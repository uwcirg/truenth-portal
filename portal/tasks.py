"""Tasks module

All tasks run via external message queue (via celery) are defined
within.

NB: a celery worker must be started for these to ever return.  See
`celery_worker.py`

"""
from sqlalchemy import and_
from datetime import datetime
from flask import current_app
from requests import Request, Session
from requests.exceptions import RequestException
from celery.utils.log import get_task_logger

from .database import db
from .dogpile import dogpile_cache
from .extensions import celery
from .models.assessment_status import overall_assessment_status
from .models.communication import Communication
from .models.communication_request import queue_outstanding_messages
from .models.reporting import get_reporting_stats
from .models.role import Role, ROLE
from .models.questionnaire_bank import QuestionnaireBank
from .models.user import User, UserRoles
from .models.scheduled_job import update_runtime

# To debug, stop the celeryd running out of /etc/init, start in console:
#   celery worker -A portal.celery_worker.celery --loglevel=debug
# Import rdb and use like pdb:
#   from celery.contrib import rdb
#   rdb.set_trace()
# Follow instructions from celery console, i.e. telnet 127.0.0.1 6900

logger = get_task_logger(__name__)


@celery.task
def add(x, y):
    return x + y


@celery.task
def info():
    return "CELERY_BROKER_URL: {} <br/> SERVER_NAME: {}".format(
        current_app.config.get('CELERY_BROKER_URL'),
        current_app.config.get('SERVER_NAME'))


@celery.task(bind=True)
def post_request(self, url, data, timeout=10, retries=3):
    """Wrap requests.post for asyncronous posts - includes timeout & retry"""
    logger.debug("task: %s retries:%s", self.request.id, self.request.retries)

    s = Session()
    req = Request('POST', url, data=data)
    prepped = req.prepare()
    try:
        resp = s.send(prepped, timeout=timeout)
        if resp.status_code < 400:
            logger.info("{} received from {}".format(resp.status_code, url))
        else:
            logger.error("{} received from {}".format(resp.status_code, url))

    except RequestException as exc:
        """Typically raised on timeout or connection error

        retry after countdown seconds unless retry threshold has been exceeded
        """
        logger.warn("{} on {}".format(exc.message, url))
        if self.request.retries < retries:
            raise self.retry(exc=exc, countdown=20)
        else:
            logger.error(
                "max retries exceeded for {}, last failure: {}".format(
                    url, exc))
    except Exception as exc:
        logger.error("Unexpected exception on {} : {}".format(url, exc))


@celery.task
def test(job_id=None):
    try:
        update_runtime(job_id)
    except Exception as exc:
        logger.error("Unexpected exception in `test` on {} : {}".format(
            job_id, exc))
    return "Test task complete."


@celery.task
def cache_reporting_stats(job_id=None):
    """Populate reporting dashboard stats cache

    Reporting stats can be a VERY expensive lookup - cached for an hour
    at a time.  This task is responsible for renewing the potenailly
    stale cache.  Expected to be called as a scheduled job.

    """
    try:
        message = "failed"
        before = datetime.now()
        dogpile_cache.invalidate(get_reporting_stats)
        dogpile_cache.refresh(get_reporting_stats)
        duration = datetime.now() - before
        message = (
            'Reporting stats updated in {0.seconds} seconds'.format(duration))
        current_app.logger.debug(message)
        update_runtime(job_id)
    except Exception as exc:
        logger.error("Unexpected exception in `cache_reporting_stats` "
                     "on {} : {}".format(job_id, exc))
    return message


@celery.task
def cache_assessment_status(job_id=None):
    """Populate assessment status cache

    Assessment status is an expensive lookup - cached for an hour
    at a time.  This task is responsible for renewing the potenailly
    stale cache.  Expected to be called as a scheduled job.

    """
    try:
        message = "failed"
        before = datetime.now()
        update_patient_loop(update_cache=True, queue_messages=False)
        duration = datetime.now() - before
        message = (
            'Assessment Cache updated in {0.seconds} seconds'.format(duration))
        current_app.logger.debug(message)
        update_runtime(job_id)
    except Exception as exc:
        logger.error("Unexpected exception in `cache_assessment_status` "
                     "on {} : {}".format(job_id, exc))
    return message


@celery.task
def prepare_communications(job_id=None):
    """Move any ready communications into prepared state """
    try:
        message = "failed"
        before = datetime.now()
        update_patient_loop(update_cache=False, queue_messages=True)
        duration = datetime.now() - before
        message = (
            'Prepared messages queued in {0.seconds} seconds'.format(duration))
        current_app.logger.debug(message)
        update_runtime(job_id)
    except Exception as exc:
        logger.error("Unexpected exception in `prepare_communications` "
                     "on {} : {}".format(job_id, exc))
    return message


def update_patient_loop(update_cache=True, queue_messages=True):
    """Function to loop over valid patients and update as per settings

    Typically called as a scheduled_job - also directly from tests
    """
    patient_role_id = Role.query.filter(
        Role.name == ROLE.PATIENT).with_entities(Role.id).first()[0]
    valid_patients = User.query.join(
        UserRoles).filter(
            and_(User.id == UserRoles.user_id,
                 User.deleted_id.is_(None),
                 UserRoles.role_id == patient_role_id))

    for user in valid_patients:
        if update_cache:
            dogpile_cache.refresh(overall_assessment_status, user.id)
        if queue_messages:
            qbd = QuestionnaireBank.most_current_qb(user=user)
            if qbd.questionnaire_bank:
                queue_outstanding_messages(
                    user=user,
                    questionnaire_bank=qbd.questionnaire_bank,
                    iteration_count=qbd.iteration)
    db.session.commit()


@celery.task
def send_queued_communications(job_id=None):
    "Look for communication objects ready to send"
    send_messages()
    update_runtime(job_id)


def send_messages():
    """Function to send all queued messages

    Typically called as a scheduled_job - also directly from tests
    """
    ready = Communication.query.filter(Communication.status == 'preparation')
    for communication in ready:
        current_app.logger.debug("Collate ready communication {}".format(
            communication))
        communication.generate_and_send()


def send_user_messages(email):
    """Send queued messages to only given user (if found) """
    count = 0
    ready = Communication.query.join(User).filter(
        Communication.status == 'preparation').filter(User.email == email)
    for communication in ready:
        current_app.logger.debug("Collate ready communication {}".format(
            communication))
        communication.generate_and_send()
        count += 1
    return "Sent {} messages to {}".format(count, email)
