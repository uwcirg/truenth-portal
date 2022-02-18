"""Reporting statistics and data module"""
from collections import defaultdict
from datetime import datetime
from smtplib import SMTPRecipientsRefused

from flask import current_app
from flask_babel import force_locale
from werkzeug.exceptions import Unauthorized

from ..audit import auditable_event
from ..cache import cache
from ..date_tools import FHIR_datetime
from ..trigger_states.models import TriggerStatesReporting
from .app_text import MailResource, SiteSummaryEmail_ATMA, app_text
from .communication import load_template_args
from .message import EmailMessage
from .organization import Organization, OrgTree
from .overall_status import OverallStatus
from .questionnaire_response import aggregate_responses
from .qb_status import QB_Status
from .qb_timeline import qb_status_visit_name
from .questionnaire_bank import visit_name
from .questionnaire_response import (
    QNR_results,
    qnr_csv_column_headers,
    generate_qnr_csv,
)
from .research_study import EMPRO_RS_ID, ResearchStudy
from .role import ROLE, Role
from .user import User, UserRoles, patients_query
from .user_consent import consent_withdrawal_dates


def adherence_report(
        requested_as_of_date, acting_user_id, include_test_role, org_id,
        research_study_id, response_format, lock_key, celery_task, limit):
    """Generates the adherence report

    Designed to be executed in a background task - all inputs and outputs are
    easily serialized (executing celery_task parent an obvious exception).

    :param requested_as_of_date: string form of as_of_date, or None to use now
    :param acting_user_id: id of user evoking request, for permission check
    :param include_test_role: set to include test patients in results
    :param org_id: set to limit to patients belonging to a branch of org tree
    :param research_study_id: research study to report on
    :param response_format: 'json' or 'csv'
    :param lock_key: name of TimeoutLock key used to throttle requests
    :param celery_task: used to update status when run as a celery task
    :param limit: limit run to first 'n' patients - used only by testing API
    :return: dictionary of results, easily stored as a task output, including
       any details needed to assist the view method

    """
    acting_user = User.query.get(acting_user_id)
    if requested_as_of_date:
        as_of_date = FHIR_datetime.parse(requested_as_of_date)
    else:
        as_of_date = datetime.utcnow()

    # If limited by org - use org and its children as filter list
    requested_orgs = (
        OrgTree().here_and_below_id(organization_id=org_id) if org_id
        else None)

    patients = patients_query(
        acting_user=acting_user,
        include_test_role=include_test_role,
        requested_orgs=requested_orgs)
    data = []
    current, total = 0, patients.count()
    for patient in patients:

        # occasionally update the celery task status if defined
        current += 1
        if limit:
            total = limit
            if current > limit:
                break

        if not current % 25 and celery_task:
            celery_task.update_state(
                state='PROGRESS', meta={'current': current, 'total': total})

        if research_study_id not in ResearchStudy.assigned_to(patient):
            continue

        try:
            acting_user.check_role('view', other_id=patient.id)
        except Unauthorized:
            # simply exclude any patients the user can't view
            continue

        qb_stats = QB_Status(
            user=patient,
            research_study_id=research_study_id,
            as_of_date=as_of_date)
        row = {
            'user_id': patient.id,
            'country': patient.organizations[0].country,
            'site': patient.organizations[0].name,
            'status': str(qb_stats.overall_status)}

        c_date, w_date = consent_withdrawal_dates(
                user=patient, research_study_id=research_study_id)
        consent = c_date if c_date else w_date
        row['consent'] = FHIR_datetime.as_fhir(consent)

        study_id = patient.external_study_id
        if study_id:
            row['study_id'] = study_id

        # if no current, try previous (as current may be expired)
        last_viable = qb_stats.current_qbd(
            even_if_withdrawn=True) or qb_stats.prev_qbd
        if not last_viable:
            # Global study default pre-started is Expired. See TN-3101
            if row['status'] == "Expired":
                row['status'] = "Not Yet Available"
            # TN-3101 include clinician even if not started on EMPRO
            if research_study_id == EMPRO_RS_ID and len(patient.clinicians) > 0:
                row['clinician'] = ';'.join(
                    clinician.display_name for clinician in
                    patient.clinicians)

        else:
            row['qb'] = last_viable.questionnaire_bank.name
            row['visit'] = visit_name(last_viable)
            if row['status'] == 'Completed':
                row['completion_date'] = FHIR_datetime.as_fhir(
                    last_viable.completed_date(patient.id))
                row['oow_completion_date'] = FHIR_datetime.as_fhir(
                    last_viable.oow_completed_date(patient.id))
            entry_method = QNR_results(
                patient,
                research_study_id=research_study_id,
                qb_ids=[last_viable.qb_id],
                qb_iteration=last_viable.iteration).entry_method()
            if entry_method:
                row['entry_method'] = entry_method

            if research_study_id == EMPRO_RS_ID:
                # Initialize trigger states reporting for patient
                ts_reporting = TriggerStatesReporting(patient_id=patient.id)

                # Add clinician and trigger data for EMPRO reports
                if len(patient.clinicians) > 0:
                    row['clinician'] = ';'.join(
                        clinician.display_name for clinician in
                        patient.clinicians)
                # Rename column header for EMPRO
                if 'completion_date' in row:
                    row['EMPRO_questionnaire_completion_date'] = (
                        row.pop('completion_date'))

                # Correct for zero index visit month in db
                visit_month = int(row['visit'].split()[-1]) - 1
                t_status = ts_reporting.latest_action_state(visit_month)
                row['clinician_status'] = (
                    t_status.title() if t_status else '')
                ht = ts_reporting.hard_triggers_for_visit(visit_month)
                row['hard_trigger_domains'] = ', '.join(ht) if ht else ''
                st = ts_reporting.soft_triggers_for_visit(visit_month)
                row['soft_trigger_domains'] = ', '.join(st) if st else ''
                da = ts_reporting.domains_accessed(visit_month)
                row['content_domains_accessed'] = ', '.join(da) if da else ''

        data.append(row)

        # as we require a full history, continue to add rows for each previous
        # visit available
        for qbd, status in qb_stats.older_qbds(last_viable):
            historic = row.copy()
            historic['status'] = status
            historic['qb'] = qbd.questionnaire_bank.name
            historic['visit'] = visit_name(qbd)
            historic['completion_date'] = (
                FHIR_datetime.as_fhir(qbd.completed_date(patient.id))
                if status == 'Completed' else '')
            historic['oow_completion_date'] = (
                FHIR_datetime.as_fhir(qbd.oow_completed_date(patient.id))
                if status == 'Completed' else '')
            entry_method = QNR_results(
                patient,
                research_study_id=research_study_id,
                qb_ids=[qbd.qb_id],
                qb_iteration=qbd.iteration).entry_method()
            if entry_method:
                historic['entry_method'] = entry_method
            else:
                historic.pop('entry_method', None)

            if research_study_id == EMPRO_RS_ID:
                # Correct for zero index visit month in db
                visit_month = int(historic['visit'].split()[-1]) - 1
                t_status = ts_reporting.latest_action_state(visit_month)
                historic['clinician_status'] = (
                    t_status.title() if t_status else '')
                ht = ts_reporting.hard_triggers_for_visit(visit_month)
                historic['hard_trigger_domains'] = ', '.join(ht) if ht else ''
                st = ts_reporting.soft_triggers_for_visit(visit_month)
                historic['soft_trigger_domains'] = ', '.join(st) if st else ''
                da = ts_reporting.domains_accessed(visit_month)
                historic['content_domains_accessed'] = (
                    ', '.join(da) if da else '')

                # Rename column header for EMPRO
                if 'completion_date' in historic:
                    historic['EMPRO_questionnaire_completion_date'] = (
                        historic.pop('completion_date'))
            data.append(historic)

        # if user is eligible for indefinite QB, add status
        qbd, status = qb_stats.indef_status()
        if qbd:
            indef = row.copy()
            indef['status'] = status
            # Indefinite doesn't have a row in the timeline, look
            # up matching date from QNRs
            indef['completion_date'] = (
                FHIR_datetime.as_fhir(qbd.completed_date(patient.id))
                if status == 'Completed' else '')
            indef['qb'] = qbd.questionnaire_bank.name
            indef['visit'] = "Indefinite"
            entry_method = QNR_results(
                patient,
                research_study_id=research_study_id,
                qb_ids=[qbd.qb_id],
                qb_iteration=qbd.iteration).entry_method()
            if entry_method:
                indef['entry_method'] = entry_method
            else:
                indef.pop('entry_method', None)
            data.append(indef)

    results = {
        'data': data,
        'lock_key': lock_key,
        'response_format': response_format,
        'required_user_id': acting_user_id}
    if response_format == 'csv':
        base_name = 'Questionnaire-Timeline-Data'
        if org_id:
            base_name = '{}-{}'.format(
                base_name,
                Organization.query.get(org_id).name.replace(' ', '-'))
        results['filename_prefix'] = base_name
        results['column_headers'] = [
            'user_id', 'study_id', 'status', 'visit', 'entry_method',
            'country', 'site', 'consent', 'completion_date',
            'oow_completion_date']
        if research_study_id == EMPRO_RS_ID:
            results['column_headers'] = [
                'user_id',
                'study_id',
                'country',
                'site',
                'visit',
                'status',
                'EMPRO_questionnaire_completion_date',
                'soft_trigger_domains',
                'hard_trigger_domains',
                'content_domains_accessed',
                'clinician',
                'clinician_status',
                ]

    return results


def research_report(
        instrument_ids, research_study_id, acting_user_id, patch_dstu2,
        request_url, response_format, lock_key, celery_task):
    """Generates the research report

    Designed to be executed in a background task - all inputs and outputs are
    easily serialized (executing celery_task parent an obvious exception).

    :param acting_user_id: id of user evoking request, for permission check
    :param instrument_ids: list of instruments to include
    :param research_study_id: study id to report on
    :param patch_dstu2: set to make bundle dstu2 compliant
    :param request_url: original request url, for inclusion in FHIR bundle
    :param response_format: 'json' or 'csv'
    :param lock_key: name of TimeoutLock key used to throttle requests
    :param celery_task: used to update status when run as a celery task
    :return: dictionary of results, easily stored as a task output, including
       any details needed to assist the view method

    """
    acting_user = User.query.get(acting_user_id)

    # Rather than call current_user.check_role() for every patient
    # in the bundle, delegate that responsibility to aggregate_responses()
    bundle = aggregate_responses(
        instrument_ids=instrument_ids,
        research_study_id=research_study_id,
        current_user=acting_user,
        patch_dstu2=patch_dstu2,
        celery_task=celery_task
    )
    bundle.update({
        'link': {
            'rel': 'self',
            'href': request_url,
        },
    })

    results = {
        'lock_key': lock_key,
        'response_format': response_format,
        'required_roles': [ROLE.RESEARCHER.value]}
    if response_format == 'csv':
        results['column_headers'] = qnr_csv_column_headers
        results['data'] = [i for i in generate_qnr_csv(bundle)]
        results['filename_prefix'] = 'qnr-data'
    else:
        results['data'] = bundle

    return results


def overdue_dates(user, research_study_id, as_of):
    """Determine if user is overdue, return details if applicable

    :param user: for whom QB Status should be evaluated
    :param research_study_id: research study in question
    :param as_of: utc datetime for comparison, typically utcnow
    :return: IF user is overdue, tuple of
     (visit_name, due_date, expired_date), otherwise (None, None, None)

    """
    na = None, None, None
    qb_status = qb_status_visit_name(user.id, research_study_id, as_of)

    if qb_status['status'] != OverallStatus.overdue:
        return na

    a_s = QB_Status(
        user, research_study_id=research_study_id, as_of_date=as_of)
    if a_s.overall_status != qb_status['status']:
        current_app.logger.error(
            "%s != %s for %s as of %s".format(
                a_s.overall_status, qb_status['status'], user.id, as_of))
    if a_s.overdue_date is None:
        return na

    return qb_status['visit_name'], a_s.due_date, a_s.expired_date


@cache.cached(timeout=60*60*12, key_prefix='overdue_stats_by_org')
def overdue_stats_by_org():
    """Generate cacheable overdue statistics

    Used in generating reports of overdue statistics.  Generates values for
    *all* patients - clients must validate permission for current_user to
    view each respective row.

    In order to avoid caching db objects, save organization's (id, name) as
    the returned dictionary key, value contains list of tuples:
      (respective user_id, study_id, due_date, expired_date)

    """
    current_app.logger.debug("CACHE MISS: {}".format(__name__))
    overdue_stats = defaultdict(list)
    now = datetime.utcnow()

    # TODO: handle research study id; currently only reporting on id==0
    research_study_id = 0
    # use system user to avoid pruning any patients during cache population
    sys = User.query.filter_by(email='__system__').one()
    for user in patients_query(acting_user=sys):
        visit, due_date, expired_date = overdue_dates(
            user, research_study_id=research_study_id, as_of=now)
        study_id = user.external_study_id or ''
        if due_date is not None:
            for org in user.organizations:
                overdue_stats[(org.id, org.name)].append((
                    user.id, study_id, visit, due_date, expired_date))
    return overdue_stats


def generate_and_send_summaries(org_id):
    from ..views.reporting import generate_overdue_table_html
    ostats = overdue_stats_by_org()
    error_emails = set()

    ot = OrgTree()
    top_org = Organization.query.get(org_id)
    if not top_org:
        raise ValueError("No org with ID {} found.".format(org_id))
    name_key = SiteSummaryEmail_ATMA.name_key(org=top_org.name)

    for staff_user in User.query.join(
            UserRoles).join(Role).filter(
            Role.name == ROLE.STAFF.value).filter(
            User.id == UserRoles.user_id).filter(
            Role.id == UserRoles.role_id).filter(
            User.deleted_id.is_(None)):
        if not(
                staff_user.email_ready()[0] and
                top_org in ot.find_top_level_orgs(staff_user.organizations)):
            continue

        args = load_template_args(user=staff_user)
        with force_locale(staff_user.locale_code):
            args['eproms_site_summary_table'] = generate_overdue_table_html(
                overdue_stats=ostats,
                user=staff_user,
                top_org=top_org,
            )
        summary_email = MailResource(
            app_text(name_key), locale_code=staff_user.locale_code,
            variables=args)
        em = EmailMessage(recipients=staff_user.email,
                          sender=current_app.config['MAIL_DEFAULT_SENDER'],
                          subject=summary_email.subject,
                          body=summary_email.body)
        try:
            em.send_message()
        except SMTPRecipientsRefused as exc:
            msg = ("Error sending site summary email to {}: "
                   "{}".format(staff_user.email, exc))

            sys = User.query.filter_by(email='__system__').first()

            auditable_event(message=msg,
                            user_id=(sys.id if sys else staff_user.id),
                            subject_id=staff_user.id,
                            context="user")

            current_app.logger.error(msg)
            for email in exc[0]:
                error_emails.add(email)

    return error_emails or None
