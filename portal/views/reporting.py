from __future__ import unicode_literals  # isort:skip

from future import standard_library # isort:skip
standard_library.install_aliases()  # noqa: E402

from collections import defaultdict
import csv
from datetime import datetime
from io import StringIO
from time import strftime

from flask import Blueprint, make_response, render_template, request
from flask_babel import gettext as _
from flask_user import roles_required

from ..extensions import oauth
from ..models.assessment_status import AssessmentStatus
from ..models.organization import Organization, OrgTree
from ..models.role import ROLE
from ..models.user import User, current_user

reporting_api = Blueprint('reporting', __name__,)


@reporting_api.route('/admin/overdue-table')
@roles_required([ROLE.STAFF.value, ROLE.INTERVENTION_STAFF.value])
@oauth.require_oauth()
def overdue_table(top_org=None):
    """View for admin access to generated email content

    Typically called by scheduled job, expected this view is only
    used for debugging & QA

    :param org_id: Top level organization ID to test
    :returns: html content typically sent directly to site resource

    """
    from ..models.reporting import overdue_stats_by_org
    if not top_org:
        org_id = request.args.get('org_id', 0)
        top_org = Organization.query.get_or_404(org_id)

    # Use values from ScheduledJob.json - just debugging utility
    # for now.  If made mainstream, pull directly from table.
    cutoff_days = []
    if top_org.name == "TrueNTH Global Registry":
        cutoff_days = [30, 60, 90]
    if top_org.name == "IRONMAN":
        cutoff_days = [7, 14, 21, 30]

    return generate_overdue_table_html(
        cutoff_days=cutoff_days, overdue_stats=overdue_stats_by_org(),
        user=current_user(), top_org=top_org)


def generate_overdue_table_html(cutoff_days, overdue_stats, user, top_org):
    cutoff_days.sort()

    day_ranges = []
    curr_min = 0
    for cd in cutoff_days:
        day_ranges.append("{}-{}".format(curr_min + 1, cd))
        curr_min = cd

    ot = OrgTree()
    rows = []
    totals = defaultdict(int)

    for org in sorted(overdue_stats, key=lambda x: x.name):
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
        org_row = [org.name]
        curr_min = 0
        row_total = 0
        for cd in cutoff_days:
            count = len([i for i in counts if ((i > curr_min) and (i <= cd))])
            org_row.append(count)
            totals[cd] += count
            row_total += count
            curr_min = cd
        org_row.append(row_total)
        rows.append(org_row)

    totalrow = [_("TOTAL")]
    row_total = 0
    for cd in cutoff_days:
        totalrow.append(totals[cd])
        row_total += totals[cd]
    totalrow.append(row_total)
    rows.append(totalrow)

    return render_template(
        'site_overdue_table.html', ranges=day_ranges, rows=rows)


def overdue(user):
    now = datetime.utcnow()
    a_s = AssessmentStatus(user, as_of_date=now)
    qb = a_s.qb_data.qbd.questionnaire_bank
    if not qb:
        return "No QB"
    trigger_date = qb.trigger_date(user)
    if not trigger_date:
        return "No trigger date"
    overdue = qb.calculated_overdue(trigger_date, as_of_date=now)
    if not overdue:
        return "No overdue date"
    return (now - overdue).days


@reporting_api.route('/admin/overdue-numbers')
@roles_required(
    [ROLE.ADMIN.value, ROLE.STAFF.value, ROLE.INTERVENTION_STAFF.value])
@oauth.require_oauth()
def generate_numbers():
    ot = OrgTree()
    results = StringIO()
    cw = csv.writer(results)

    cw.writerow((
        "User ID", "Email", "Questionnaire Bank", "Status",
        "Days Overdue", "Organization"))

    for user in User.query.filter_by(active=True):
        if (user.has_role(ROLE.PATIENT.value) and not
                user.has_role(ROLE.TEST.value)):
            a_s = AssessmentStatus(user, as_of_date=datetime.utcnow())
            email = (
                user.email.encode('ascii', 'ignore') if user.email else None)
            od = overdue(user)
            qb = a_s.qb_name
            for org in user.organizations:
                top = ot.find_top_level_orgs([org], first=True)
                org_name = "{}: {}".format(
                    top.name, org.name) if top else org.name
                cw.writerow((
                    user.id, email, qb, a_s.overall_status, od, org_name))

    filename = 'overdue-numbers-{}.csv'.format(strftime('%Y_%m_%d-%H_%M'))
    output = make_response(results.getvalue())
    output.headers['Content-Disposition'] = "attachment; filename={}".format(
        filename)
    output.headers['Content-type'] = "text/csv"
    return output
