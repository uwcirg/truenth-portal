"""Reporting statistics and data module"""
from collections import defaultdict
from datetime import datetime
from flask import current_app
from flask_babel import gettext as _

from ..dogpile import dogpile_cache
from .fhir import CC
from .intervention import Intervention
from .organization import OrgTree
from .procedure_codes import known_treatment_started
from .procedure_codes import known_treatment_not_started
from .questionnaire_bank import QuestionnaireBank
from .role import ROLE
from .user import User


@dogpile_cache.region('hourly')
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
        if user.has_role(ROLE.TEST):
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

        if user.has_role(ROLE.PATIENT) or user.has_role(ROLE.PARTNER):
            for interv in interventions:
                desc = interv.description
                if interv.name == 'decision_support_p3p':
                    desc = 'Decision Support P3P'
                if interv.quick_access_check(user):
                    stats['intervention_access'][desc] += 1
                if interv in user.interventions:
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
    qb = QuestionnaireBank.most_current_qb(user).questionnaire_bank
    if not qb:
        return 0
    trigger_date = qb.trigger_date(user)
    overdue = qb.calculated_overdue(trigger_date)
    return (datetime.utcnow() - overdue).days if overdue else 0


def overdue_stats_by_org():
    overdue_stats = defaultdict(list)
    for user in User.query.filter_by(active=True):
        if user.has_role(ROLE.TEST):
            continue
        overdue = calculate_days_overdue(user)
        if overdue > 0:
            for org in user.organizations:
                overdue_stats[org].append(overdue)
    return overdue_stats


def generate_overdue_table_html(cutoff_days, overdue_stats, user, top_org):
    cutoff_days.sort()

    title = _(u"Days Overdue")
    col0_header = _(u"Site")
    html = u"""
    <table>
    <caption><b>{}</b></caption>
    <thead>
    <tr>
        <th>{}</th>
    """.format(title, col0_header)

    curr_min = 0
    for cd in cutoff_days:
        daystr = _(u"Days")
        rangestr = "{}-{}".format(curr_min + 1, cd)
        html += "<th>{} {}</th>".format(rangestr, daystr)
        curr_min = cd
    colx_header = _(u"Total")
    html += u"""
        <th>{}</th>
    </tr>
    </thead>
    <tbody>
    """.format(colx_header)

    ot = OrgTree()

    totals = defaultdict(int)
    for org in sorted(overdue_stats, key=lambda x: x.id):
        if top_org and not ot.at_or_below_ids(top_org.id, [org.id]):
            continue
        user_accessible = False
        for user_org in user.organizations:
            if ot.at_or_below_ids(user_org.id, [org.id]):
                user_accessible = True
                break
        if not user_accessible:
            continue
        counts = overdue_stats[org]
        html += u'<tr><td>{}</td>'.format(org.name)
        curr_min = 0
        row_total = 0
        for cd in cutoff_days:
            count = len([i for i in counts if ((i > curr_min) and (i <= cd))])
            html += "<td>{}</td>".format(count)
            totals[cd] += count
            row_total += count
            curr_min = cd
        html += u'<td>{}</td></tr>'.format(row_total)

    totalstr = _(u"TOTAL")
    html += u'<tr><td>{}</td>'.format(totalstr)
    row_total = 0
    for cd in cutoff_days:
        html += "<td>{}</td>".format(totals[cd])
        row_total += totals[cd]
    html += u'<td>{}</td></tr>'.format(row_total)

    html += u"</tbody></table>"

    return html
