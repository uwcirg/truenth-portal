from __future__ import unicode_literals  # isort:skip

from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402

from collections import defaultdict
import csv
from datetime import datetime
from io import StringIO
from time import strftime

from flask import (
    Blueprint,
    jsonify,
    make_response,
    render_template,
    request,
    url_for,
)
from flask_babel import gettext as _
from flask_user import roles_required

from ..date_tools import FHIR_datetime
from ..extensions import oauth
from ..models.organization import Organization, OrgTree
from ..models.qb_status import QB_Status
from ..models.role import ROLE
from ..models.user import current_user, patients_query

reporting_api = Blueprint('reporting', __name__)


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

    for org_id, org_name in sorted(overdue_stats, key=lambda x: x[1]):
        if top_org and not ot.at_or_below_ids(top_org.id, [org_id]):
            continue
        user_accessible = False
        for user_org in user.organizations:
            if ot.at_or_below_ids(user_org.id, [org_id]):
                user_accessible = True
                break
        if not user_accessible:
            continue
        counts = overdue_stats[(org_id, org_name)]
        org_row = [org_name]
        source_row = [org_name+'[user_ids]']
        curr_min = 0
        row_total = 0
        for cd in cutoff_days:
            uids = []
            for days_overdue, user_id in counts:
                if days_overdue > curr_min and days_overdue <= cd:
                    uids.append(user_id)
            count = len(
                [i for i, uid in counts if ((i > curr_min) and (i <= cd))])
            org_row.append(count)
            source_row.append(uids)
            totals[cd] += count
            row_total += count
            curr_min = cd
        org_row.append(row_total)
        rows.append(org_row)
        # Uncomment the following row to display user ids behind numbers
        # rows.append(source_row)

    totalrow = [_("TOTAL")]
    row_total = 0
    for cd in cutoff_days:
        totalrow.append(totals[cd])
        row_total += totals[cd]
    totalrow.append(row_total)
    rows.append(totalrow)

    return render_template(
        'site_overdue_table.html', ranges=day_ranges, rows=rows)


@reporting_api.route('/admin/overdue-numbers')
@roles_required(
    [ROLE.ADMIN.value, ROLE.STAFF.value, ROLE.INTERVENTION_STAFF.value])
@oauth.require_oauth()
def generate_numbers():

    def overdue(qstats):
        now = datetime.utcnow()
        overdue = qstats.overdue_date
        if not overdue:
            return "No overdue date"
        return (now - overdue).days

    ot = OrgTree()
    results = StringIO()
    cw = csv.writer(results)

    cw.writerow((
        "User ID", "Email", "Questionnaire Bank", "Status",
        "Days Overdue", "Organization"))

    for user in patients_query(
            acting_user=current_user(), include_test_role=False):
        a_s = QB_Status(user, as_of_date=datetime.utcnow())
        email = (
            user.email.encode('ascii', 'ignore') if user.email else None)
        od = overdue(a_s)
        qb = a_s.current_qbd().questionnaire_bank.name
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


@reporting_api.route('/api/report/questionnaire_status')
@roles_required(
    [ROLE.ADMIN.value, ROLE.STAFF.value, ROLE.INTERVENTION_STAFF.value])
@oauth.require_oauth()
def questionnaire_status():
    """Return ad hoc JSON or CSV listing questionnaire_status

    ---
    tags:
      - Report
      - Questionnaire

    operationId: questionnaire_status
    parameters:
      - name: org_id
        in: query
        description: optional TrueNTH organization ID used to limit results
          to patients belonging to given organization identifier, and given
          organization's child organizations
        required: false
        type: integer
        format: int64
      - name: as_of_date
        in: query
        description: optional query string param to request status at a
          different (UTC) point in time.  Defaults to now
        required: false
        type: string
        format: date-time
      - name: include_test_role
        in: query
        description: optional query string param to add patients with the
          test role to the results.  Excluded by default
        required: false
        type: string
      - name: format
        in: query
        description: expects json or csv, defaults to json if not provided
        required: false
        type: string
    produces:
      - application/json
      - text/csv
    responses:
      200:
        description:
          Returns JSON of the available questionnaire bank status for matching
          set of users
      400:
        description: invalid query parameters
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id

    """
    from ..tasks import adherence_report_task

    # This frequently takes over a minute to produce.  Generate a serializable
    # form of all args for reliable hand off to a background task.
    kwargs = {
        'requested_as_of_date': request.args.get('as_of_date'),
        'acting_user_id': current_user().id,
        'include_test_role': request.args.get('include_test_role', False),
        'org_id': request.args.get('org_id'),
        'response_format': request.args.get('format', 'json').lower()
    }

    # Hand the task off to the job queue, and return 202 with URL for
    # checking the status of the task
    task = adherence_report_task.apply_async(kwargs=kwargs)
    return jsonify({}), 202, {'Location': url_for(
        'portal.task_status', task_id=task.id, _external=True)}
