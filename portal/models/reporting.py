"""Reporting statistics and data module"""
import functools
from collections import defaultdict, namedtuple
from datetime import datetime, timedelta
from smtplib import SMTPRecipientsRefused

from flask import current_app
from flask_babel import force_locale
from werkzeug.exceptions import Unauthorized

from ..audit import auditable_event
from ..cache import cache
from ..database import db
from ..date_tools import report_format
from ..timeout_lock import ADHERENCE_DATA_KEY, CacheModeration
from ..trigger_states.models import TriggerStatesReporting
from .adherence_data import AdherenceData, sorted_adherence_data
from .app_text import MailResource, SiteSummaryEmail_ATMA, app_text
from .communication import load_template_args
from .message import EmailMessage
from .organization import Organization, OrgTree
from .overall_status import OverallStatus
from .questionnaire_response import aggregate_responses
from .qb_status import QB_Status
from .qb_timeline import QBT, qb_status_visit_name
from .questionnaire_bank import visit_name
from .questionnaire_response import (
    QNR_results,
    qnr_csv_column_headers,
    generate_qnr_csv,
)
from .research_study import BASE_RS_ID, EMPRO_RS_ID, ResearchStudy
from .role import ROLE, Role
from .user import User, UserRoles, patients_query
from .user_consent import consent_withdrawal_dates


def debug_msg(patient_id, message):
    """helper to generate common format debug message for challenging issue"""
    current_app.logger.debug(f"adherence_cache debug {patient_id}: {message}")


def update_patient_adherence_data(patient_id):
    """Cache invalidation and force rebuild for given patient's adherence data

    NB - any timeline or questionnaire response data changes are invalidated and
    updated as part of `invalidate_users_QBT()`.  This function is for edge cases
    such as changing a user's study-id.
    """
    patient = User.query.get(patient_id)
    AdherenceData.query.filter(AdherenceData.patient_id==patient_id).delete()
    for rs_id in ResearchStudy.assigned_to(patient):
        single_patient_adherence_data(patient_id=patient_id, research_study_id=rs_id)


def single_patient_adherence_data(patient_id, research_study_id):
    """Update any missing (from cache) adherence data for patient

    NB: all changes are side effects, persisted in adherence_data table.
    To avoid race conditions where a user's timeline triggers an update
    of adherence_data which triggers a user's timeline update, maintain
    a set of patient_ids and only update the adherence data for any given
    patient 1/hour.  Given the scheduled jobs that run and validate
    against expiration in a user's adherence record, skipped runs will
    get caught next cycle.

    :returns: number of added rows
    """
    # ignore non-patient requests
    patient = User.query.get(patient_id)
    if not patient.has_role(ROLE.PATIENT.value):
        return

    debug_msg(patient_id, "enter single_patient_adherence_data()")

    # keep patient list data in sync
    from .patient_list import patient_list_update_patient
    patient_list_update_patient(patient_id=patient_id, research_study_id=research_study_id)

    as_of_date = datetime.utcnow()
    cache_moderation = CacheModeration(key=ADHERENCE_DATA_KEY.format(
        patient_id=patient_id,
        research_study_id=research_study_id))
    if cache_moderation.run_recently():
        debug_msg(patient_id, "exit as run_recently()")
        return 0
    cache_moderation.run_now()

    def patient_data(patient):
        """Returns dict of patient data regardless of qnr status"""
        # Basic patient data
        org = patient.organizations[0] if patient.organizations else None
        d = {
            'user_id': patient.id,
            'country': org.country if org else "",
            'site': org.name if org else "",
            'site_code': org.sitecode if org else ""
        }
        study_id = patient.external_study_id
        if study_id:
            d['study_id'] = study_id

        # Consent date
        c_date, w_date = consent_withdrawal_dates(
                user=patient, research_study_id=research_study_id)
        consent = c_date if c_date else w_date
        d['consent'] = report_format(consent)

        # EMPRO always gets clinician(s)
        if research_study_id == EMPRO_RS_ID and len(
                [c for c in patient.clinicians]) > 0:
            d['clinician'] = ';'.join(
                clinician.display_name for clinician in
                patient.clinicians)
        return d

    def general_row_detail(row, patient, qbd):
        """Add general (either study) data for given (patient, qbd)"""
        # purge values that may have previous row data set and aren't certain
        for key in "oow_completion_date", "entry_method", "visit":
            row.pop(key, None)

        row['qb'] = qbd.questionnaire_bank.name

        # if withdrawn, include a row with that and little more
        if row['status'] == 'Withdrawn':
            # use date of withdrawal for "completion date"
            _, withdrawal_date = consent_withdrawal_dates(
                user=patient, research_study_id=research_study_id)
            row['completion_date'] = report_format(withdrawal_date)
            return
        row['visit'] = visit_name(qbd)
        row['completion_date'] = (
            report_format(qbd.completed_date(patient.id))
            if row['status'] == 'Completed' else '')
        entry_method = QNR_results(
            patient,
            research_study_id=research_study_id,
            qb_ids=[qbd.qb_id],
            qb_iteration=qbd.iteration).entry_method()
        if entry_method:
            row['entry_method'] = entry_method

    def empro_row_detail(row, ts_reporting):
        """Add EMPRO specifics"""
        if not ts_reporting:
            return

        # Rename column header for EMPRO
        if 'completion_date' in row:
            row['EMPRO_questionnaire_completion_date'] = (
                row.pop('completion_date'))

        # If withdrawn, the rest is unreliable
        if row['status'] == 'Withdrawn':
            return

        # Correct for zero index visit month in db
        visit_month = int(row['visit'].split()[-1]) - 1
        t_status = ts_reporting.latest_action_state(visit_month)
        row['clinician_status'] = (
            t_status.title() if t_status else "")
        row['clinician_survey_completion_date'] = (
            report_format(
                ts_reporting.resolution_authored_from_visit(visit_month))
            or "")
        row['delayed_by_holiday'] = (
            ts_reporting.resolution_delayed_by_holiday(visit_month) or ""
        )
        ht = ts_reporting.hard_triggers_for_visit(visit_month)
        row['hard_trigger_domains'] = ', '.join(ht) if ht else ""
        oo = ts_reporting.opted_out_domains_for_visit(visit_month)
        row['opted_out_domains'] = ', '.join(oo) if oo else ""
        st = ts_reporting.soft_triggers_for_visit(visit_month)
        row['soft_trigger_domains'] = ', '.join(st) if st else ""
        da = ts_reporting.domains_accessed(visit_month)
        row['content_domains_accessed'] = ', '.join(da) if da else ""

    added_rows = 0
    qb_stats = QB_Status(
        user=patient,
        research_study_id=research_study_id,
        as_of_date=as_of_date)
    # if no current, try previous (as current may be expired)
    last_viable = qb_stats.current_qbd(
        even_if_withdrawn=True) or qb_stats.prev_qbd
    if not last_viable:
        debug_msg(patient_id, "no last viable")

    if last_viable:
        rs_visit = AdherenceData.rs_visit_string(
            research_study_id, visit_name(last_viable))
        if AdherenceData.fetch(patient_id=patient.id, rs_id_visit=rs_visit):
            # latest already in cache, done with this patient
            debug_msg(patient_id, f"exit finding {rs_visit} as last viable")
            return added_rows

    # build up data until we find valid cache for patient's history
    status = str(qb_stats.overall_status)
    row = patient_data(patient)
    row["status"] = status
    if status == "Expired" and research_study_id == EMPRO_RS_ID:
        # Expired status ambiguous for EMPRO study.
        # - If the last available questionnaire in the study is present in
        #   the user's timeline and the expired date has passed, it is
        #   legitimately "Expired".
        # - Otherwise, due to complex business rules around delayed
        #   start/availability mark as "Not Yet Available"
        exp_row = QBT.query.filter(QBT.research_study_id == EMPRO_RS_ID).filter(
            QBT.user_id == patient.id).filter(
            QBT.status == 'expired').filter(
            QBT.qb_iteration == 10).first()  # baseline is 1, 11 iterations base 0
        if not exp_row or exp_row.at > as_of_date:
            row["status"] = "Not Yet Available"

    ts_reporting = (
        TriggerStatesReporting(patient_id=patient.id)
        if research_study_id == EMPRO_RS_ID else None)
    if last_viable:
        general_row_detail(row, patient, last_viable)
        empro_row_detail(row, ts_reporting)

        # latest is only valid for a day, unless the user withdrew
        valid_for = 30 if row['status'] in ('Expired', 'Withdrawn') else 1
        AdherenceData.persist(
            patient_id=patient.id,
            rs_id_visit=rs_visit,
            valid_for_days=valid_for,
            data=row)
        added_rows += 1

        # if the last row was withdrawn, add any completed visits beyond
        # date of withdrawal
        if row["status"] == 'Withdrawn':
            withdrawal_date = (
                row['completion_date'] if 'completion_date' in row
                else row['EMPRO_questionnaire_completion_date'])
            missing_qbts = []
            completed_after_withdrawn = QBT.query.filter(
                QBT.at > withdrawal_date).filter(
                QBT.status == OverallStatus.completed).filter(
                QBT.research_study_id == research_study_id).filter(
                QBT.user_id == patient.id).order_by(QBT.at)
            for qbt in completed_after_withdrawn:
                missing_qbts.append((qbt.at, qbt.qbd()))

            # one more special case!  the withdrawn visit was completed
            # but BEFORE the user withdrew.  the qb_status accurately sees
            # the visit as withdrawn, and wrote that to the last row, but
            # failed to write out the completed status first.
            pre_wd_visit_cd = last_viable.completed_date(patient.id)
            if pre_wd_visit_cd and not [
                    x for x, y in missing_qbts if x == pre_wd_visit_cd]:
                missing_qbts.append((pre_wd_visit_cd, last_viable))

            for at, qbd in missing_qbts:
                row['status'] = 'Completed'  # overwrite withdrawn state
                general_row_detail(row, patient, qbd)
                empro_row_detail(row, ts_reporting)
                rs_visit = AdherenceData.rs_visit_string(
                    research_study_id, row['visit'], post_withdrawn=True)
                AdherenceData.persist(
                    patient_id=patient.id,
                    rs_id_visit=rs_visit,
                    valid_for_days=30,
                    data=row)
                added_rows += 1

    # as we require a full history, continue to add rows for each previous
    for qbd, status in qb_stats.older_qbds(last_viable):
        rs_visit = AdherenceData.rs_visit_string(
            research_study_id, visit_name(qbd))
        debug_msg(patient_id, f"adding historic {rs_visit} row")

        # once we find cached_data, the rest of the user's history is likely
        # good, but best to verify nothing is stale
        if AdherenceData.fetch(patient_id=patient.id, rs_id_visit=rs_visit):
            debug_msg(patient_id, f"skip as {rs_visit} found")
            continue

        historic = row.copy()
        historic['status'] = status
        general_row_detail(historic, patient, qbd)
        empro_row_detail(historic, ts_reporting)
        AdherenceData.persist(
            patient_id=patient.id,
            rs_id_visit=rs_visit,
            valid_for_days=30,
            data=historic)
        added_rows += 1

    # if user is eligible for indefinite QB, add status
    qbd = None
    if research_study_id == BASE_RS_ID:
        qbd, status = qb_stats.indef_status()
    if qbd:
        rs_visit = "0:Indefinite"
        cached_data = AdherenceData.fetch(
            patient_id=patient.id, rs_id_visit=rs_visit)

        if not cached_data:
            indef = row.copy()
            indef['status'] = status
            # Indefinite doesn't have a row in the timeline, look
            # up matching date from QNRs
            indef['completion_date'] = (
                report_format(qbd.completed_date(patient.id))
                if status == 'Completed' else '')
            indef["oow_completion_date"] = ""
            indef['qb'] = qbd.questionnaire_bank.name
            indef['visit'] = "Indefinite"
            entry_method = QNR_results(
                patient,
                research_study_id=research_study_id,
                qb_ids=[qbd.qb_id],
                qb_iteration=qbd.iteration).entry_method()
            indef['entry_method'] = entry_method if entry_method else ""
            AdherenceData.persist(
                patient_id=patient.id,
                rs_id_visit=rs_visit,
                valid_for_days=30,
                data=indef)
            added_rows += 1

    return added_rows


def cache_adherence_data(
        include_test_role=False,
        org_id=None,
        research_study_id=0,
        limit=0,
        patient_id=None,
        job_id=None,
        manual_run=None):
    """Populates the adherence data cache for timely reports

    Designed to be executed as a routine job.  Initially removes any rows that
    have expired (or will do so in a day to avoid race conditions).  Then works
    through all patients updating any missing rows.

    :param include_test_role: set to include test patients in results
    :param org_id: set to limit to patients belonging to a branch of org tree
    :param research_study_id: research study to report on
    :param limit: limit run to first 'n' added rows.  effective throttle to
      limit scope and runtime of task; next run will pick up next block
    :param patient_id: use to process only a single patient
    :param job_id: noise ignored from scheduled job fixture
    :param manual_run: noise ignored from scheduled job fixture
    :return: dict including number of rows updated in adherence_data table and
      if limit was hit

    """
    from ..tasks import cache_single_patient_adherence_data
    # For building cache, use system account; skip privilege checks
    acting_user = User.query.filter_by(email='__system__').one()
    as_of_date = datetime.utcnow()

    # Purge any rows that have or will soon expire
    valid = (as_of_date + timedelta(hours=1))
    AdherenceData.query.filter(AdherenceData.valid_till < valid).delete()
    db.session.commit()

    def patient_generator():
        """Generator for requested patients, updates job status as needed"""
        # If limited by org - use org and its children as filter list
        requested_orgs = (
            OrgTree().here_and_below_id(organization_id=org_id) if org_id
            else None)

        id_filter = [patient_id] if patient_id else None
        patients = patients_query(
            acting_user=acting_user,
            include_test_role=include_test_role,
            research_study_id=research_study_id,
            requested_orgs=requested_orgs,
            filter_by_ids=id_filter)
        for patient in patients:
            yield patient

    added_rows = 0
    for patient in patient_generator():
        if limit and added_rows > limit:
            current_app.logger.info(
                "pre-mature exit caching adherence data having hit limit")
            break
        # queue patient's adherence cache refresh as a separate job
        kwargs = {
            'patient_id': patient.id,
            'research_study_id': research_study_id}
        cache_single_patient_adherence_data.apply_async(
            kwargs=kwargs, retry=False)

    return {'added': added_rows, 'limit_hit': limit and added_rows > limit}


def adherence_report(
        requested_as_of_date, acting_user_id, include_test_role, org_id,
        research_study_id, response_format, lock_key, celery_task, limit):
    """Generates adherence report from previously populated adherence_data

    Designed to be executed in a background task - all inputs and outputs are
    easily serialized (excluding celery_task parent an obvious exception).

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

    def patient_generator():
        """Generator for requested patients, updates job status as needed"""
        # If limited by org - use org and its children as filter list
        requested_orgs = (
            OrgTree().here_and_below_id(organization_id=org_id) if org_id
            else None)

        patients = patients_query(
            acting_user=acting_user,
            include_test_role=include_test_role,
            research_study_id=research_study_id,
            requested_orgs=requested_orgs)
        current = 0
        total = limit if limit else patients.count()
        for patient in patients:

            # occasionally update the celery task status if defined
            current += 1
            if current > total:
                return

            if not current % 25 and celery_task:
                celery_task.update_state(
                    state='PROGRESS',
                    meta={'current': current, 'total': total})
            try:
                acting_user.check_role('view', other_id=patient.id)
            except Unauthorized:
                # simply exclude any patients the user can't view
                continue

            yield patient


    data = []
    for patient in patient_generator():
        patient_data = sorted_adherence_data(patient.id, research_study_id)
        data.extend(patient_data)

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
            'country', 'site', 'site_code', 'consent', 'completion_date',
            'oow_completion_date']
        if research_study_id == EMPRO_RS_ID:
            results['column_headers'] = [
                'user_id',
                'study_id',
                'country',
                'site',
                'site_code',
                'visit',
                'status',
                'EMPRO_questionnaire_completion_date',
                'soft_trigger_domains',
                'hard_trigger_domains',
                'opted_out_domains',
                'content_domains_accessed',
                'clinician',
                'clinician_status',
                'clinician_survey_completion_date',
                'delayed_by_holiday',
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
      (respective user_id, study_id, visit, due_date, expired_date)

    """
    current_app.logger.debug("CACHE MISS: {}".format(__name__))
    overdue_stats = defaultdict(list)
    now = datetime.utcnow()

    # use system user to avoid pruning any patients during cache population
    sys = User.query.filter_by(email='__system__').one()
    for user in patients_query(acting_user=sys):
        visit, due_date, expired_date = overdue_dates(
            user, research_study_id=BASE_RS_ID, as_of=now)
        study_id = user.external_study_id or ''
        if due_date is not None:
            for org in user.organizations:
                overdue_stats[(org.id, org.name)].append((
                    user.id, study_id, visit, due_date, expired_date))
    return overdue_stats


EmproOverdueRow = namedtuple('EmproOverdueRow', [
    'user_id',
    'study_id',
    'clinician_status',
    'clinician_survey_completion_date',
    'clinician',
    'status',
    'completion_date',
    'due_date',
    'visit',
])


def empro_overdue_stats():
    """EMPRO overdue statistics

    Used in generating reports of overdue statistics.  Generate values for
    *all* EMPRO eligible patients (one row per patient).

    Clients must validate permission for current_user to view each respective
    row. In order to avoid caching db objects, save organization's (id, name)
    as the returned dictionary key, value contains list of `EmproOverdueRow`
    namedtuples (see below)

    """
    overdue_stats = defaultdict(list)
    now = datetime.utcnow()

    # use system user to avoid pruning any patients during cache population
    sys = User.query.filter_by(email='__system__').one()

    for user in patients_query(acting_user=sys, research_study_id=EMPRO_RS_ID):
        qb_stats = QB_Status(
            user=user,
            research_study_id=EMPRO_RS_ID,
            as_of_date=now)
        # if no current, try previous (as current may be expired)
        qbd = qb_stats.current_qbd(
            even_if_withdrawn=True) or qb_stats.prev_qbd

        for org in user.organizations:
            # without a current or previous QBD - not much to report
            if qbd is None:
                row = EmproOverdueRow(
                    user_id=user.id,
                    study_id=user.external_study_id or "",
                    status="Not yet started",
                    clinician=';'.join(
                        clinician.display_name for clinician in
                        user.clinicians),
                    clinician_status="",
                    clinician_survey_completion_date="",
                    completion_date="",
                    due_date="",
                    visit="",
                )
            else:
                # Correct "Month 12" format to zero indexed int
                visit = visit_name(qbd)
                visit_month = int(visit.split()[-1]) - 1

                # Initialize trigger states reporting for patient
                ts_reporting = TriggerStatesReporting(patient_id=user.id)
                t_status = ts_reporting.latest_action_state(visit_month)
                clinician_status = t_status.title() if t_status else ""
                if not clinician_status:
                    if qb_stats.overall_status in (OverallStatus.withdrawn, OverallStatus.expired):
                        clinician_status = str(qb_stats.overall_status)
                    elif qb_stats.overall_status in (OverallStatus.due, OverallStatus.overdue):
                        clinician_status = "EMPRO not yet completed"
                    else:
                        raise ValueError(f"unexpected status {qb_stats.overall_status}")

                row = EmproOverdueRow(
                    user_id=user.id,
                    study_id=user.external_study_id or '',
                    visit=visit,
                    status=str(qb_stats.overall_status),
                    completion_date=report_format(
                        qbd.completed_date(user.id)) or "",
                    due_date=report_format(
                        qbd.relative_start) or "",
                    clinician=';'.join(
                        clinician.display_name for clinician in
                        user.clinicians),
                    clinician_status=clinician_status,
                    clinician_survey_completion_date=report_format(
                        ts_reporting.resolution_authored_from_visit(
                            visit_month)) or ""
                )
            overdue_stats[(org.id, org.name)].append(row)

    def stat_compare(x, y):
        """custom sort to keep overdue and due at top of list"""

        ordered_stat_options = (
            "overdue",
            "required",
            "due",
            "completed",
            "empro not yet completed",
            "not applicable",
            "expired",
            "",
            "withdrawn")

        try:
            x_i = ordered_stat_options.index(x.clinician_status.lower())
            y_i = ordered_stat_options.index(y.clinician_status.lower())
        except ValueError:
            raise ValueError(
                f"{x.clinician_status} or {y.clinician_status} not expected")

        if x_i == y_i:
            return 0
        if x_i < y_i:
            return -1
        return 1

    # For each org, order rows by clinician status, with any `overdue`
    # values coming first
    for key in overdue_stats.keys():
        items = overdue_stats[key]
        overdue_stats[key] = sorted(
            items, key=functools.cmp_to_key(stat_compare))

    return overdue_stats


def generate_and_send_summaries(org_id, research_study_id):
    from ..views.reporting import (
        generate_overdue_table_html,
        generate_EMPRO_overdue_table_html)

    if research_study_id == BASE_RS_ID:
        ostats = overdue_stats_by_org()
        html_generation_function = generate_overdue_table_html

        def staff_generator():
            # Staff centric report - yields each staff user for
            # email including all respective orgs for given user.
            for user in User.query.join(
                    UserRoles).join(Role).filter(
                    Role.name == ROLE.STAFF.value).filter(
                    User.id == UserRoles.user_id).filter(
                    Role.id == UserRoles.role_id).filter(
                    User.deleted_id.is_(None)):
                yield user, None

    elif research_study_id == EMPRO_RS_ID:
        ostats = empro_overdue_stats()
        html_generation_function = generate_EMPRO_overdue_table_html
        org_ids_in_report = [i[0] for i in ostats.keys()]

        def staff_generator():
            # Org centric report - yields each staff and org as
            # each email is specific to one site
            from ..views.clinician import clinician_query
            sys = User.query.filter_by(email='__system__').one()

            for org_id in org_ids_in_report:
                staff_users = clinician_query(
                    acting_user=sys, org_filter=[org_id], include_staff=True)
                for user in staff_users:
                    yield user, Organization.query.get(org_id)

    else:
        raise ValueError(f"unknown research study {research_study_id}")

    error_emails = set()

    ot = OrgTree()
    top_org = Organization.query.get(org_id)
    if not top_org:
        raise ValueError("No org with ID {} found.".format(org_id))
    name_key = SiteSummaryEmail_ATMA.name_key(
        org=top_org.name, research_study=research_study_id)

    for staff_user, child_org in staff_generator():
        if not(
                staff_user.email_ready()[0] and
                top_org in ot.find_top_level_orgs(staff_user.organizations)):
            continue

        args = load_template_args(user=staff_user)
        with force_locale(staff_user.locale_code or current_app.config['DEFAULT_LOCALE']):
            args['eproms_site_summary_table'] = html_generation_function(
                overdue_stats=ostats,
                user=staff_user,
                top_org=child_org or top_org,
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
            db.session.add(em)
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

    db.session.commit()
    return error_emails or None
