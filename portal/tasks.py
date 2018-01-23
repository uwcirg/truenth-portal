"""Tasks module

All tasks run via external message queue (via celery) are defined
within.

NB: a celery worker must be started for these to ever return.  See
`celery_worker.py`

"""
from celery.utils.log import get_task_logger
from datetime import datetime
from flask import current_app
from functools import wraps
import json
from requests import Request, Session
from requests.exceptions import RequestException
from smtplib import SMTPRecipientsRefused
from sqlalchemy import and_
from traceback import format_exc

from .audit import auditable_event
from .database import db
from .dogpile_cache import dogpile_cache
from factories.celery import create_celery
from factories.app import create_app
from .models.assessment_status import invalidate_assessment_status_cache
from .models.assessment_status import overall_assessment_status
from .models.app_text import app_text, MailResource, SiteSummaryEmail_ATMA
from .models.communication import Communication, load_template_args
from .models.communication_request import queue_outstanding_messages
from .models.message import EmailMessage
from .models.notification import Notification, UserNotification
from .models.organization import Organization, OrgTree
from .models.research_protocol import ResearchProtocol
from .models.reporting import get_reporting_stats, overdue_stats_by_org
from .models.reporting import generate_overdue_table_html
from .models.role import Role, ROLE
from .models.questionnaire_bank import QuestionnaireBank
from .models.user import User, UserRoles
from .models.scheduled_job import check_active, update_job_status

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
        Role.name == ROLE.PATIENT).with_entities(Role.id).first()[0]
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
            if not user.email or '@' not in user.email:
                # can't send to users w/o legit email
                continue
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


def send_user_messages(email, force_update=False):
    """Send queued messages to only given user (if found)

    @param email: to process
    @param force_update: set True to force reprocessing of cached
    data and queue any messages previously overlooked.

    Triggers a send for any messages found in a prepared state ready
    for transmission.

    """
    if force_update:
        user = User.query.filter(User.email == email).one()
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
        Communication.status == 'preparation').filter(User.email == email)
    for communication in ready:
        current_app.logger.debug("Collate ready communication {}".format(
            communication))
        communication.generate_and_send()
        db.session.commit()
        count += 1
    message = "Sent {} messages to {}".format(count, email)
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


def generate_and_send_summaries(cutoff_days, org_id):
    ostats = overdue_stats_by_org()
    cutoffs = [int(i) for i in cutoff_days.split(',')]
    error_emails = set()

    ot = OrgTree()
    top_org = Organization.query.get(org_id)
    if not top_org:
        raise ValueError("No org with ID {} found.".format(org_id))
    name_key = SiteSummaryEmail_ATMA.name_key(org=top_org.name)

    for user in User.query.filter_by(deleted_id=None).all():
        if (user.has_role(ROLE.STAFF) and user.email and (u'@' in user.email)
                and (top_org in ot.find_top_level_org(user.organizations))):
            args = load_template_args(user=user)
            args['eproms_site_summary_table'] = generate_overdue_table_html(
                cutoff_days=cutoffs,
                overdue_stats=ostats,
                user=user,
                top_org=top_org)
            summary_email = MailResource(app_text(name_key), variables=args)
            em = EmailMessage(recipients=user.email,
                              sender=current_app.config['MAIL_DEFAULT_SENDER'],
                              subject=summary_email.subject,
                              body=summary_email.body)
            try:
                em.send_message()
            except SMTPRecipientsRefused as exc:
                msg = ("Error sending site summary email to {}: "
                       "{}".format(user.email, exc))

                sys = User.query.filter_by(email='__system__').first()

                auditable_event(message=msg,
                                user_id=(sys.id if sys else user.id),
                                subject_id=user.id,
                                context="user")

                current_app.logger.error(msg)
                for email in exc[0]:
                    error_emails.add(email)

    return error_emails or None


@celery.task
@scheduled_task
def deactivate_tous_task(**kwargs):
    """Require users to re-consent to their initial consent

    Scheduled task, delegates work to `deactivate_tous()`

    """
    return deactivate_tous(**kwargs)


def deactivate_tous(**kwargs):
    """Deactivate matching consents

    Optional kwargs:
    :param types: ToU types for which to invalidate agreements
    :param organization: Provide name of organization to restrict
    to respective set of users.  All child orgs implicitly included.
    :param roles: Restrict to users with given roles; defaults to
    (ROLE.PATIENT, ROLE.STAFF, ROLE.STAFF_ADMIN)

    """
    types = kwargs.get('types')
    sys = User.query.filter_by(email='__system__').first()

    if not sys:
        raise ValueError("No system user found")

    require_orgs = None
    if kwargs.get('organization'):
        org_name = kwargs.get('organization')
        org = Organization.query.filter(Organization.name == org_name).first()
        if not org:
            raise ValueError("No such organization: {}".format(org_name))
        require_orgs = set(OrgTree().here_and_below_id(org.id))

    require_roles = set(
        kwargs.get('roles', (ROLE.PATIENT, ROLE.STAFF, ROLE.STAFF_ADMIN)))
    for role in require_roles:
        if not Role.query.filter(Role.name == role).first():
            raise ValueError("No such role: {}".format(role))

    for user in User.query.filter(User.deleted_id.is_(None)):
        if require_roles.isdisjoint([r.name for r in user.roles]):
            continue
        if require_orgs and require_orgs.isdisjoint(
                [o.id for o in user.organizations]):
            continue
        user.deactivate_tous(acting_user=sys, types=types)


@celery.task
@scheduled_task
def notify_users(**kwargs):
    "Create UserNotifications for a given Notification"
    notif_name = kwargs.get('notification')
    notif = Notification.query.filter_by(name=notif_name).first()
    if not notif:
        raise ValueError("Notification `{}` not found".format(notif_name))

    roles = kwargs.get('roles')

    for user in User.query.filter(User.deleted_id.is_(None)):
        if set([role.name for role in user.roles]).isdisjoint(set(roles)):
            continue
        if not UserNotification.query.filter_by(
                user_id=user.id, notification_id=notif.id).count():
            un = UserNotification(user_id=user.id,
                                  notification_id=notif.id)
            db.session.add(un)
    db.session.commit()
