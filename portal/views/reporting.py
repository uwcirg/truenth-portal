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
    Response,
    jsonify,
    make_response,
    render_template,
    request,
)
from flask_babel import gettext as _
from flask_user import roles_required
from werkzeug.exceptions import Unauthorized

from ..date_tools import FHIR_datetime
from ..extensions import oauth
from ..models.fhir import bundle_results
from ..models.organization import Organization, OrgTree
from ..models.questionnaire_bank import visit_name
from ..models.qb_status import QB_Status
from ..models.role import ROLE
from ..models.user import active_patients, current_user
from ..models.user_consent import latest_consent

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

    for user in active_patients(include_test_role=False):
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

    if request.args.get('as_of_date'):
        as_of_date = FHIR_datetime.parse(request.args.get('as_of_date'))
    else:
        as_of_date = datetime.utcnow()

    # If limited by org - grab org and all it's children as required list
    org_id = request.args.get('org_id')
    require_orgs = (
        OrgTree().here_and_below_id(organization_id=org_id) if org_id
        else None)

    # Obtain list of qualifying patients
    include_test_role = request.args.get('include_test_role', False)
    patients = active_patients(
        include_test_role=include_test_role,
        require_orgs=require_orgs)

    acting_user = current_user()
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
        last_viable = qb_stats.current_qbd() or qb_stats.prev_qbd
        if last_viable:
            row['qb'] = last_viable.questionnaire_bank.name
            row['visit'] = visit_name(last_viable)

        results.append(row)

        # as we require a full history, continue to add rows for each previous
        # visit available
        for qbd, status in qb_stats.older_qbds(last_viable):
            historic = row.copy()
            historic['status'] = status
            historic['qb'] = qbd.questionnaire_bank.name
            historic['visit'] = visit_name(qbd)
            results.append(historic)

    if request.args.get('format', 'json').lower() == 'csv':
        def gen(items):
            desired_order = [
                'user_id', 'study_id', 'status', 'visit', 'site', 'consent']
            yield ','.join(desired_order) + '\n'  # header row
            for i in items:
                yield ','.join(
                    [str(i.get(k, "")) for k in desired_order]) + '\n'
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
