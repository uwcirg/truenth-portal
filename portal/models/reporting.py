"""Reporting statistics and data module"""
from collections import defaultdict
from datetime import datetime
from smtplib import SMTPRecipientsRefused
from time import strftime

from flask import Response, current_app, jsonify
from flask_babel import force_locale
from werkzeug.exceptions import Unauthorized

from ..audit import auditable_event
from ..dogpile_cache import dogpile_cache
from ..date_tools import FHIR_datetime
from .app_text import MailResource, SiteSummaryEmail_ATMA, app_text
from .clinical_constants import CC
from .communication import load_template_args
from .fhir import bundle_results
from .intervention import Intervention
from .message import EmailMessage
from .organization import Organization, OrgTree
from .overall_status import OverallStatus
from .procedure_codes import (
    known_treatment_not_started,
    known_treatment_started,
)
from .qb_status import QB_Status
from .questionnaire_bank import visit_name
from .questionnaire_response import QNR_results
from .role import ROLE
from .user import User, patients_query
from .user_consent import latest_consent


@dogpile_cache.region('reporting_cache_region')
def get_reporting_stats():
    """Cachable interface for expensive reporting data queries

    The following code is only run on a cache miss.

    """
    current_app.logger.debug("CACHE MISS: {}".format(__name__))
    stats = {}
    stats['roles'] = defaultdict(int)
    stats['patients'] = defaultdict(int)
    stats['interventions'] = defaultdict(int)
    stats['intervention_access'] = defaultdict(int)
    stats['intervention_reports'] = defaultdict(int)
    stats['organizations'] = defaultdict(int)
    stats['registrations'] = []
    stats['encounters'] = defaultdict(list)

    interventions = Intervention.query.all()

    for user in User.query.filter_by(active=True):
        if user.has_role(ROLE.TEST.value):
            continue

        for role in user.roles:
            stats['roles'][role.name] += 1
            if role.name == 'patient':
                if not any((obs.codeable_concept == CC.BIOPSY
                            and obs.value_quantity.value)
                           for obs in user.observations):
                    stats['patients']['pre-dx'] += 1
                elif known_treatment_not_started(user):
                    stats['patients']['dx-nt'] += 1
                elif known_treatment_started(user):
                    stats['patients']['dx-t'] += 1
                if any((obs.codeable_concept == CC.PCaLocalized
                        and obs.value_quantity == CC.FALSE_VALUE)
                       for obs in user.observations):
                    stats['patients']['meta'] += 1

        if (user.has_role(ROLE.PATIENT.value) or
                user.has_role(ROLE.PARTNER.value)):
            for interv in interventions:
                desc = interv.description
                if interv.name == 'decision_support_p3p':
                    desc = 'Decision Support P3P'
                elif interv.name == 'community_of_wellness':
                    desc = 'Community of Wellness'
                if interv.quick_access_check(user):
                    stats['intervention_access'][desc] += 1
                if ((interv in user.interventions) and not interv.public_access
                        and not interv.access_strategies):
                    stats['interventions'][desc] += 1
                if (any(doc.intervention == interv for doc in user.documents)):
                    stats['intervention_reports'][desc] += 1

        if not user.organizations:
            stats['organizations']['Unspecified'] += 1
        else:
            for org in user.organizations:
                stats['organizations'][org.name] += 1

        stats['registrations'].append(user.registered)

        for enc in user.encounters:
            if enc.auth_method == 'password_authenticated':
                st = enc.start_time
                stats['encounters']['all'].append(st)
                for interv in user.interventions:
                    if interv.name == 'decision_support_p3p':
                        stats['encounters']["Decision Support P3P"].append(st)
                    else:
                        stats['encounters'][interv.description].append(st)

    return stats


def adherence_report(
        as_of_date, acting_user_id, include_test_role, org_id, format):
    acting_user = User.query.get(acting_user_id)
    # If limited by org - grab org and all it's children as filter list
    requested_orgs = (
        OrgTree().here_and_below_id(organization_id=org_id) if org_id
        else None)

    patients = patients_query(
        acting_user=acting_user,
        include_test_role=include_test_role,
        requested_orgs=requested_orgs)
    results = []
    for patient in patients:
        if len(patient.organizations) == 0:
            # Very unlikely we want to include patients w/o at least
            # one org, skip this patient
            continue

        try:
            acting_user.check_role('view', other_id=patient.id)
        except Unauthorized:
            # simply exclude any patients the user can't view
            continue

        qb_stats = QB_Status(user=patient, as_of_date=as_of_date)
        row = {
            'user_id': patient.id,
            'site': patient.organizations[0].name,
            'status': str(qb_stats.overall_status)}

        consent = latest_consent(user=patient)
        if consent:
            row['consent'] = FHIR_datetime.as_fhir(consent.acceptance_date)

        study_id = patient.external_study_id
        if study_id:
            row['study_id'] = study_id

        # if no current, try previous (as current may be expired)
        last_viable = qb_stats.current_qbd(
            even_if_withdrawn=True) or qb_stats.prev_qbd
        if last_viable:
            row['qb'] = last_viable.questionnaire_bank.name
            row['visit'] = visit_name(last_viable)
            entry_method = QNR_results(
                patient, last_viable.qb_id,
                last_viable.iteration).entry_method()
            if entry_method:
                row['entry_method'] = entry_method

        results.append(row)

        # as we require a full history, continue to add rows for each previous
        # visit available
        for qbd, status in qb_stats.older_qbds(last_viable):
            historic = row.copy()
            historic['status'] = status
            historic['qb'] = qbd.questionnaire_bank.name
            historic['visit'] = visit_name(qbd)
            entry_method = QNR_results(
                patient, qbd.qb_id, qbd.iteration).entry_method()
            if entry_method:
                historic['entry_method'] = entry_method
            else:
                historic.pop('entry_method', None)
            results.append(historic)

    if format == 'csv':
        def gen(items):
            desired_order = [
                'user_id', 'study_id', 'status', 'visit', 'site', 'consent']
            yield ','.join(desired_order) + '\n'  # header row
            for i in items:
                yield ','.join(
                    ['"{}"'.format(i.get(k, "")) for k in desired_order]
                ) + '\n'

        # default file base title
        base_name = 'Questionnaire-Timeline-Data'
        if org_id:
            base_name = '{}-{}'.format(
                base_name,
                Organization.query.get(org_id).name.replace(' ', '-'))
        filename = '{}-{}.csv'.format(base_name, strftime('%Y_%m_%d-%H_%M'))

        return Response(
            gen(results),
            headers={
                'Content-Disposition': 'attachment;filename={}'.format(
                    filename),
                'Content-type': "text/csv"}
        )
    else:
        return jsonify(bundle_results(elements=results))


def calculate_days_overdue(user):
    now = datetime.utcnow()
    a_s = QB_Status(user, as_of_date=now)
    if a_s.overall_status in (
            OverallStatus.completed, OverallStatus.expired,
            OverallStatus.partially_completed):
        return 0
    overdue = a_s.overdue_date
    return (datetime.utcnow() - overdue).days if overdue else 0


@dogpile_cache.region('reporting_cache_region')
def overdue_stats_by_org():
    """Generate cacheable stats by org

    In order to avoid caching db objects, save organization's (id, name) as
    the returned dictionary key, value contains list of tuples, (number of
    days overdue and the respective user_id)

    """
    current_app.logger.debug("CACHE MISS: {}".format(__name__))
    overdue_stats = defaultdict(list)
    for user in User.query.filter_by(active=True):
        if (user.has_role(ROLE.TEST.value) or not
                user.has_role(ROLE.PATIENT.value)):
            continue
        overdue = calculate_days_overdue(user)
        if overdue > 0:
            for org in user.organizations:
                overdue_stats[(org.id, org.name)].append((overdue, user.id))
    return overdue_stats


def generate_and_send_summaries(cutoff_days, org_id):
    from ..views.reporting import generate_overdue_table_html
    ostats = overdue_stats_by_org()
    cutoffs = [int(i) for i in cutoff_days.split(',')]
    error_emails = set()

    ot = OrgTree()
    top_org = Organization.query.get(org_id)
    if not top_org:
        raise ValueError("No org with ID {} found.".format(org_id))
    name_key = SiteSummaryEmail_ATMA.name_key(org=top_org.name)

    for user in User.query.filter_by(deleted_id=None).all():
        if not (user.has_role(ROLE.STAFF.value) and user.email_ready()[0]
                and (top_org in ot.find_top_level_orgs(user.organizations))):
            continue

        args = load_template_args(user=user)
        with force_locale(user.locale_code):
            args['eproms_site_summary_table'] = generate_overdue_table_html(
                cutoff_days=cutoffs,
                overdue_stats=ostats,
                user=user,
                top_org=top_org,
            )
        summary_email = MailResource(
            app_text(name_key), locale_code=user.locale_code, variables=args)
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
