"""Reporting statistics and data module"""
from collections import defaultdict
from datetime import datetime
from smtplib import SMTPRecipientsRefused

from flask import current_app
from flask_babel import force_locale

from ..audit import auditable_event
from ..dogpile_cache import dogpile_cache
from ..views.reporting import generate_overdue_table_html
from .app_text import MailResource, SiteSummaryEmail_ATMA, app_text
from .assessment_status import AssessmentStatus
from .clinical_constants import CC
from .communication import load_template_args
from .intervention import Intervention
from .message import EmailMessage
from .organization import Organization, OrgTree
from .procedure_codes import (
    known_treatment_not_started,
    known_treatment_started,
)
from .role import ROLE
from .user import User


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

        if not user.organizations.count():
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


def calculate_days_overdue(user):
    now = datetime.utcnow()
    a_s = AssessmentStatus(user, as_of_date=now)
    if a_s.overall_status in ('Completed', 'Expired', 'Partially Completed'):
        return 0
    qb = a_s.qb_data.qbd.questionnaire_bank
    if not qb:
        return 0
    trigger_date = qb.trigger_date(user)
    if not trigger_date:
        return 0
    overdue = qb.calculated_overdue(trigger_date, as_of_date=now)
    return (datetime.utcnow() - overdue).days if overdue else 0


@dogpile_cache.region('reporting_cache_region')
def overdue_stats_by_org():
    current_app.logger.debug("CACHE MISS: {}".format(__name__))
    overdue_stats = defaultdict(list)
    for user in User.query.filter_by(active=True):
        if (user.has_role(ROLE.TEST.value) or not
                user.has_role(ROLE.PATIENT.value)):
            continue
        overdue = calculate_days_overdue(user)
        if overdue > 0:
            for org in user.organizations:
                overdue_stats[org].append(overdue)
    return overdue_stats


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
