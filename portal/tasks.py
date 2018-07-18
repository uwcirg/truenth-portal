"""Tasks module

All tasks run via external message queue (via celery) are defined
within.

NB: a celery worker must be started for these to ever return.  See
`celery_worker.py`

"""
from datetime import datetime
from functools import wraps
import json
from traceback import format_exc

from celery.utils.log import get_task_logger
from flask import current_app
from requests import Request, Session
from requests.exceptions import RequestException
from sqlalchemy import and_

from .database import db
from .dogpile_cache import dogpile_cache
from .factories.app import create_app
from .factories.celery import create_celery
from .models.assessment_status import (
    invalidate_assessment_status_cache,
    overall_assessment_status,
)
from .models.communication import Communication
from .models.communication_request import queue_outstanding_messages
from .models.questionnaire_bank import QuestionnaireBank
from .models.reporting import generate_and_send_summaries, get_reporting_stats
from .models.role import ROLE, Role
from .models.scheduled_job import check_active, update_job_status
from .models.tou import update_tous
from .models.user import User, UserRoles

# To debug, stop the celeryd running out of /etc/init, start in console:
#   celery worker -A portal.celery_worker.celery --loglevel=debug
# Import rdb and use like pdb:
#   from celery.contrib import rdb
#   rdb.set_trace()
# Follow instructions from celery console, i.e. telnet 127.0.0.1 6900

logger = get_task_logger(__name__)

celery = create_celery(create_app())


def scheduled_task(func):
    @wraps(func)
    def call_and_update(*args, **kwargs):
        job_id = kwargs.get('job_id')
        manual_run = kwargs.get('manual_run')

        if not manual_run and job_id and not check_active(job_id):
            message = "Job id `{}` inactive.".format(job_id)
            logger.debug(message)
            return message

        try:
            before = datetime.now()
            output = func(*args, **kwargs)
            duration = datetime.now() - before
            message = ('{} ran in {} '
                       'seconds.'.format(func.__name__, duration.seconds))
            if output:
                message += " {}".format(output)
            current_app.logger.debug(message)
        except Exception as exc:
            message = ("Unexpected exception in `{}` "
                       "on {} : {}".format(func.__name__, job_id, exc))
            logger.error(message)
            logger.error(format_exc())

        if job_id:
            update_job_status(job_id, status=message)

        return message
    return call_and_update


@celery.task(name="tasks.add")
def add(x, y):
    return x + y


@celery.task(name="tasks.info")
def info():
    return "BROKER_URL: {} <br/> SERVER_NAME: {}".format(
        current_app.config.get('BROKER_URL'),
        current_app.config.get('SERVER_NAME'))


@celery.task(name="tasks.post_request", bind=True)
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
@scheduled_task
def test(**kwargs):
    return "Test"


@celery.task
@scheduled_task
def test_args(*args, **kwargs):
    alist = ",".join(args)
    klist = json.dumps(kwargs)
    return "{}|{}".format(",".join(args), json.dumps(kwargs))


@celery.task
@scheduled_task
def cache_reporting_stats(**kwargs):
    """Populate reporting dashboard stats cache

    Reporting stats can be a VERY expensive lookup - cached for an hour
    at a time.  This task is responsible for renewing the potentially
    stale cache.  Expected to be called as a scheduled job.

    """
    dogpile_cache.invalidate(get_reporting_stats)
    dogpile_cache.refresh(get_reporting_stats)


@celery.task
@scheduled_task
def cache_assessment_status(**kwargs):
    """Populate assessment status cache

    Assessment status is an expensive lookup - cached for an hour
    at a time.  This task is responsible for renewing the potentially
    stale cache.  Expected to be called as a scheduled job.

    """
    update_patient_loop(update_cache=True, queue_messages=False)


@celery.task
@scheduled_task
def prepare_communications(**kwargs):
    """Move any ready communications into prepared state """
    update_patient_loop(update_cache=False, queue_messages=True)


def update_patient_loop(update_cache=True, queue_messages=True):
    """Function to loop over valid patients and update as per settings

    Typically called as a scheduled_job - also directly from tests
    """
    patient_role_id = Role.query.filter(
        Role.name == ROLE.PATIENT.value).with_entities(Role.id).first()[0]
    valid_patients = User.query.join(
        UserRoles).filter(
            and_(User.id == UserRoles.user_id,
                 User.deleted_id.is_(None),
                 UserRoles.role_id == patient_role_id))

    now = datetime.utcnow()
    for user in valid_patients:
        if update_cache:
            dogpile_cache.invalidate(overall_assessment_status, user.id)
            dogpile_cache.refresh(overall_assessment_status, user.id)
        if queue_messages:
            qbd = QuestionnaireBank.most_current_qb(user=user, as_of_date=now)
            if qbd.questionnaire_bank:
                queue_outstanding_messages(
                    user=user,
                    questionnaire_bank=qbd.questionnaire_bank,
                    iteration_count=qbd.iteration)
    db.session.commit()


@celery.task
@scheduled_task
def send_queued_communications(**kwargs):
    "Look for communication objects ready to send"
    send_messages()


def send_messages():
    """Function to send all queued messages

    Typically called as a scheduled_job - also directly from tests
    """
    ready = Communication.query.filter(Communication.status == 'preparation')
    for communication in ready:
        current_app.logger.debug("Collate ready communication {}".format(
            communication))
        communication.generate_and_send()
        db.session.commit()


def send_user_messages(user, force_update=False):
    """Send queued messages to only given user (if found)

    @param user: to email
    @param force_update: set True to force reprocessing of cached
    data and queue any messages previously overlooked.

    Triggers a send for any messages found in a prepared state ready
    for transmission.

    """
    ready, reason = user.email_ready()
    if not ready:
        raise ValueError("Cannot send messages to {user}; {reason}".format(
            user=user, reason=reason))

    if force_update:
        invalidate_assessment_status_cache(user_id=user.id)
        qbd = QuestionnaireBank.most_current_qb(
            user=user, as_of_date=datetime.utcnow())
        if qbd.questionnaire_bank:
            queue_outstanding_messages(
                user=user,
                questionnaire_bank=qbd.questionnaire_bank,
                iteration_count=qbd.iteration)
    count = 0
    ready = Communication.query.join(User).filter(
        Communication.status == 'preparation').filter(User == user)
    for communication in ready:
        current_app.logger.debug("Collate ready communication {}".format(
            communication))
        communication.generate_and_send()
        db.session.commit()
        count += 1
    message = "Sent {} messages to {}".format(count, user.email)
    if force_update:
        message += " after forced update"
    return message


@celery.task
@scheduled_task
def send_questionnaire_summary(**kwargs):
    "Generate and send a summary of questionnaire counts to all Staff in org"
    cutoff_days = kwargs['cutoff_days']
    org_id = kwargs['org_id']
    error_emails = generate_and_send_summaries(cutoff_days, org_id)
    if error_emails:
        return ('\nUnable to reach recipient(s): '
                '{}'.format(', '.join(error_emails)))


@celery.task
@scheduled_task
def update_tous_task(**kwargs):
    """Job to manage updates for various ToUs

    Scheduled task, see docs in ``tou.update_tous()``

    """
    return update_tous(**kwargs)


@celery.task
@scheduled_task
def token_watchdog(**kwargs):
    """Clean up stale tokens and alert service sponsors if nearly expired"""
    from .models.auth import token_janitor
    error_emails = token_janitor()
    if error_emails:
        return '\nUnable to reach recipient(s): {}'.format(
            ', '.join(error_emails))
