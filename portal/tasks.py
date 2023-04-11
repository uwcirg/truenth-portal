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
import redis
from requests import Request, Session
from requests.exceptions import RequestException
from sqlalchemy import and_

from .database import db
from .factories.app import create_app
from .factories.celery import create_celery
from .models.communication import Communication
from .models.communication_request import queue_outstanding_messages
from .models.message import Newsletter
from .models.qb_status import QB_Status
from .models.qb_timeline import invalidate_users_QBT, update_users_QBT
from .models.reporting import (
    adherence_report,
    generate_and_send_summaries,
    research_report,
)
from .models.research_study import ResearchStudy
from .models.role import ROLE, Role
from .models.scheduled_job import check_active, update_job_status
from .models.tou import update_tous
from .models.user import User, UserRoles

# To debug, stop the celeryd running out of /etc/init, start in console:
#   celery worker -A portal.celery_worker.celery --loglevel=debug
# or for tasks in the low_priority queue:
#   celery worker -A portal.celery_worker.celery -Q low_priority \
#       --loglevel=debug
#
# Import rdb and use like pdb:
#   from celery.contrib import rdb
#   rdb.set_trace()
# Follow instructions from celery console, i.e. telnet 127.0.0.1 6900

logger = get_task_logger(__name__)

celery = create_celery(create_app())
LOW_PRIORITY = 'low_priority'


def scheduled_task(func):
    @wraps(func)
    def call_and_update(*args, **kwargs):
        job_id = kwargs.get('job_id')
        manual_run = kwargs.get('manual_run')

        if not manual_run and job_id and not check_active(job_id):
            message = "Job id `{}` inactive.".format(job_id)
            current_app.logger.debug(message)
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
            current_app.logger.error(message)
            current_app.logger.error(format_exc())

        if job_id:
            update_job_status(job_id, status=message)

        return message

    return call_and_update


@celery.task(name="tasks.add")
def add(x, y):
    return x + y


@celery.task(name="tasks.info", queue=LOW_PRIORITY)
def info():
    return "BROKER_URL: {} <br/> SERVER_NAME: {}".format(
        current_app.config.get('BROKER_URL'),
        current_app.config.get('SERVER_NAME'))


@celery.task(bind=True, track_started=True, queue=LOW_PRIORITY)
def adherence_report_task(self, **kwargs):
    current_app.logger.debug("launch adherence report task: %s", self.request.id)
    kwargs['celery_task'] = self
    return adherence_report(**kwargs)


@celery.task(bind=True, track_started=True, queue=LOW_PRIORITY)
def research_report_task(self, **kwargs):
    current_app.logger.debug("launch research report task: %s", self.request.id)
    kwargs['celery_task'] = self
    return research_report(**kwargs)


@celery.task(name="tasks.post_request", bind=True)
def post_request(self, url, data, timeout=10, retries=3):
    """Wrap requests.post for asynchronous posts - includes timeout & retry"""
    current_app.logger.debug("task: %s retries:%s", self.request.id, self.request.retries)

    s = Session()
    req = Request('POST', url, data=data)
    prepped = req.prepare()
    try:
        resp = s.send(prepped, timeout=timeout)
        if resp.status_code < 400:
            current_app.logger.info("{} received from {}".format(resp.status_code, url))
        else:
            current_app.logger.error("{} received from {}".format(resp.status_code, url))

    except RequestException as exc:
        """Typically raised on timeout or connection error

        retry after countdown seconds unless retry threshold has been exceeded
        """
        current_app.logger.warn("{} on {}".format(exc.message, url))
        if self.request.retries < retries:
            raise self.retry(exc=exc, countdown=20)
        else:
            current_app.logger.error(
                "max retries exceeded for {}, last failure: {}".format(
                    url, exc))
    except Exception as exc:
        current_app.logger.error("Unexpected exception on {} : {}".format(url, exc))


@celery.task
@scheduled_task
def test(**kwargs):
    return "Test"


@celery.task
@scheduled_task
def test_args(*args, **kwargs):
    return "{}|{}".format(",".join(args), json.dumps(kwargs))


@celery.task(queue=LOW_PRIORITY)
@scheduled_task
def cache_assessment_status(**kwargs):
    """Populate assessment status cache

    Assessment status is an expensive lookup - cached for an hour
    at a time.  This task is responsible for renewing the potentially
    stale cache.  Expected to be called as a scheduled job.

    """
    update_patient_loop(update_cache=True, queue_messages=False, as_task=True)


@celery.task(queue=LOW_PRIORITY)
@scheduled_task
def prepare_communications(**kwargs):
    """Move any ready communications into prepared state """
    update_patient_loop(
        update_cache=False, queue_messages=True, as_task=True)


def update_patient_loop(
        update_cache=True, queue_messages=True, as_task=False):
    """Function to loop over valid patients and update as per settings

    Typically called as a scheduled_job - also directly from tests
    """
    patient_role_id = Role.query.filter(
        Role.name == ROLE.PATIENT.value).with_entities(Role.id).first()[0]
    valid_patients = User.query.join(UserRoles).filter(and_(
        User.id == UserRoles.user_id,
        User.deleted_id.is_(None),
        UserRoles.role_id == patient_role_id)).with_entities(User.id)

    patients = [r[0] for r in valid_patients.all()]
    j = 0
    batchsize = current_app.config['UPDATE_PATIENT_TASK_BATCH_SIZE']

    while True:
        sublist = patients[j:j+batchsize]
        if not sublist:
            break
        current_app.logger.debug("Sending sublist {} to update_patients".format(sublist))
        j += batchsize
        kwargs = {
            'patient_list': sublist, 'update_cache': update_cache,
            'queue_messages': queue_messages}
        if as_task:
            update_patients_task.apply_async(priority=9, kwargs=kwargs)
        else:
            update_patients(**kwargs)


@celery.task(name="tasks.update_patients_task", queue=LOW_PRIORITY)
def update_patients_task(patient_list, update_cache, queue_messages):
    """Task form - wraps call to testable function `update_patients` """
    update_patients(patient_list, update_cache, queue_messages)


def update_patients(patient_list, update_cache, queue_messages):
    now = datetime.utcnow()
    for user_id in patient_list:
        user = User.query.get(user_id)
        for research_study_id in ResearchStudy.assigned_to(user):
            if update_cache:
                update_users_QBT(user_id, research_study_id)
            if queue_messages:
                qbstatus = QB_Status(user, research_study_id, now)
                qbd = qbstatus.current_qbd()
                if qbd:
                    queue_outstanding_messages(
                        user=user,
                        questionnaire_bank=qbd.questionnaire_bank,
                        iteration_count=qbd.iteration)

            db.session.commit()


@celery.task(queue=LOW_PRIORITY)
@scheduled_task
def send_newsletter(**kwargs):
    """Construct newsletter content and email out"""
    org_id = kwargs['org_id']
    research_study_id = kwargs['research_study_id']
    nl = Newsletter(
        org_id=kwargs['org_id'],
        research_study_id=kwargs['research_study_id'],
        content_key=kwargs['newsletter'])
    error_emails = nl.transmit()
    if error_emails:
        return ('\nUnable to reach recipient(s): '
                '{}'.format(', '.join(error_emails)))


@celery.task(queue=LOW_PRIORITY)
@scheduled_task
def send_queued_communications(**kwargs):
    """Look for communication objects ready to send"""
    send_messages(as_task=True)


def send_messages(as_task=False):
    """Function to send all queued messages

    Typically called as a scheduled_job - also directly from tests
    """
    ready = Communication.query.filter(
        Communication.status == 'preparation').with_entities(Communication.id)

    for communication_id in ready:
        if as_task:
            send_communication_task.apply_async(
                priority=9, kwargs={'communication_id': communication_id})
        else:
            send_communication(communication_id)


@celery.task(name="tasks.send_communication_task", queue=LOW_PRIORITY)
def send_communication_task(communication_id):
    send_communication(communication_id)


def send_communication(communication_id):
    communication = Communication.query.get(communication_id)
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

    users_rs_ids = ResearchStudy.assigned_to(user)

    if force_update:
        for rs_id in users_rs_ids:
            invalidate_users_QBT(user_id=user.id, research_study_id=rs_id)
            qbd = QB_Status(
                user=user,
                research_study_id=rs_id,
                as_of_date=datetime.utcnow()).current_qbd()
            if qbd:
                queue_outstanding_messages(
                    user=user,
                    questionnaire_bank=qbd.questionnaire_bank,
                    iteration_count=qbd.iteration)
    count = 0
    ready = Communication.query.join(User).filter(
        Communication.status == 'preparation').filter(User.id == user.id)
    for communication in ready:
        communication.generate_and_send()
        db.session.commit()
        count += 1
    message = "Sent {} messages to {}".format(count, user.email)
    if force_update:
        message += " after forced update"
    return message


@celery.task(queue=LOW_PRIORITY)
@scheduled_task
def send_questionnaire_summary(**kwargs):
    """Generate and send a summary of overdue patients to all Staff in org"""
    org_id = kwargs['org_id']
    research_study_id = kwargs['research_study_id']
    run_dates = kwargs.get('run_dates')
    if run_dates:
        # Workaround to run only on certain dates, where cron syntax fails,
        # such as "every 3rd monday".  Set crontab schedule to run every
        # monday and restrict run_dates to 15..21
        today = datetime.utcnow().day
        if today not in run_dates:
            # wrong week - skip out
            return "run_dates suggest NOP this week"

    error_emails = generate_and_send_summaries(org_id, research_study_id)
    if error_emails:
        return ('\nUnable to reach recipient(s): '
                '{}'.format(', '.join(error_emails)))


@celery.task(queue=LOW_PRIORITY)
@scheduled_task
def update_tous_task(**kwargs):
    """Job to manage updates for various ToUs

    Scheduled task, see docs in ``tou.update_tous()``

    """
    return update_tous(**kwargs)


@celery.task(queue=LOW_PRIORITY)
@scheduled_task
def token_watchdog(**kwargs):
    """Clean up stale tokens and alert service sponsors if nearly expired"""
    from .models.auth import token_janitor
    error_emails = token_janitor()
    if error_emails:
        return '\nUnable to reach recipient(s): {}'.format(
            ', '.join(error_emails))


@celery.task
@scheduled_task
def celery_beat_health_check(**kwargs):
    """Refreshes self-expiring redis value for /healthcheck of celerybeat"""

    rs = redis.StrictRedis.from_url(current_app.config['REDIS_URL'])
    return rs.setex(
        name='last_celery_beat_ping',
        time=current_app.config['LAST_CELERY_BEAT_PING_EXPIRATION_TIME'],
        value=str(datetime.utcnow()),
    )


@celery.task(queue=LOW_PRIORITY)
@scheduled_task
def celery_beat_health_check_low_priority_queue(**kwargs):
    """Refreshes self-expiring redis value for /healthcheck of celerybeat"""

    rs = redis.StrictRedis.from_url(current_app.config['REDIS_URL'])
    return rs.setex(
        name='last_celery_beat_ping_low_priority_queue',
        time=10*current_app.config['LAST_CELERY_BEAT_PING_EXPIRATION_TIME'],
        value=str(datetime.utcnow()),
    )


@celery.task(name="tasks.extract_observations_task", queue=LOW_PRIORITY)
def extract_observations_task(questionnaire_response_id):
    """Task wrapper for extract_observations"""
    from portal.trigger_states.empro_states import extract_observations
    extract_observations(questionnaire_response_id)


@celery.task(queue=LOW_PRIORITY)
@scheduled_task
def process_triggers_task(**kwargs):
    """Task form - wraps call to testable function `fire_trigger_events` """
    # Include within function as not all applications include the blueprint
    from portal.trigger_states.empro_states import fire_trigger_events
    fire_trigger_events()


@celery.task()
@scheduled_task
def raise_background_exception_task(**kwargs):
    """Manually trigger to verify job raised exceptions are caught"""
    if kwargs.get("exception_type") == "RuntimeError":
        raise RuntimeError("intentional RuntimeError raised from task")
    if kwargs.get("exception_type") == "ValueError":
        raise ValueError("intentional ValueError raised from task")
    raise Exception("intentional Exception raised from task")
