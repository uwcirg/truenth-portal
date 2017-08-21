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

from .dogpile import dogpile_cache
from .extensions import celery
from .models.assessment_status import overall_assessment_status
from .models.role import Role, ROLE
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
    update_runtime(job_id)
    return "Test task complete."


@celery.task
def cache_assessment_status(job_id=None):
    """Populate assessment status cache

    Assessment status is an expensive lookup - cached for an hour
    at a time.  This task is responsible for renewing the potenailly
    stale cache.  Expected to be called as a scheduled job.

    """
    before = datetime.now()
    current_app.logger.debug(__name__)
    patient_role_id = Role.query.filter(
        Role.name == ROLE.PATIENT).with_entities(Role.id).first()[0]
    users_with_potential_assessment_status = User.query.join(
        UserRoles).filter(
            and_(User.id == UserRoles.user_id,
                 User.deleted_id == None,
                 UserRoles.role_id == patient_role_id))

    for user in users_with_potential_assessment_status:
        dogpile_cache.refresh(
            overall_assessment_status, user.id)
        for consent in user.all_consents:
            dogpile_cache.refresh(
                overall_assessment_status, user.id, consent.id)
    duration = datetime.now() - before
    message = 'Assessment Cache updated in {0.seconds} seconds'.format(
        duration)
    current_app.logger.debug(message)
    update_runtime(job_id)
    return message
