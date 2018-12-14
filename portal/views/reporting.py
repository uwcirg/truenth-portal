from __future__ import unicode_literals  # isort:skip

from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402

from collections import defaultdict
import csv
from datetime import datetime
from io import StringIO
from time import strftime

from flask import Blueprint, jsonify, make_response, render_template, request
from flask_babel import gettext as _
from flask_user import roles_required

from ..date_tools import FHIR_datetime
from ..extensions import oauth
from ..models.fhir import bundle_results
from ..models.organization import Organization, OrgTree, UserOrganization
from ..models.overall_status import OverallStatus
from ..models.questionnaire_bank import visit_name
from ..models.qb_status import QB_Status
from ..models.role import Role, ROLE
from ..models.user import User, UserRoles, current_user
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

    for user in User.query.filter_by(active=True):
        if (user.has_role(ROLE.PATIENT.value) and not
                user.has_role(ROLE.TEST.value)):
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
    """Return ad hoc JSON listing questionnaire_status

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
    produces:
      - application/json
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

    # Obtain list of qualifying patients (not marked test)
    # TODO: refactor this common query need to model and replace
    # the less efficient similar usage elsewhere...
    test_user_ids = UserRoles.query.join(Role).filter(
        UserRoles.role_id == Role.id).filter(
        Role.name == ROLE.TEST.value).with_entities(UserRoles.user_id)
    patients = User.query.filter(User.active.is_(True)).join(
        UserRoles).filter(User.id == UserRoles.user_id).join(
        Role).filter(Role.name == ROLE.PATIENT.value).filter(
        ~User.id.in_(test_user_ids))

    # If limited by org - grab org and all it's children, and refine query
    org_id = request.args.get('org_id')
    if org_id:
        limit_orgs = OrgTree().here_and_below_id(organization_id=org_id)
        patients = patients.join(UserOrganization).filter(
            User.id == UserOrganization.user_id).filter(
            UserOrganization.organization_id.in_(limit_orgs))

    # Todo: confirm current_user has view on all patients
    results = []
    for patient in patients:
        if not patient.organizations.first():
            # Very unlikely we want to include patients w/o at least
            # one org, skip this patient
            continue

        qb_stats = QB_Status(user=patient, as_of_date=as_of_date)
        row = {
            'user_id': patient.id,
            'site': patient.organizations.first().name,
            'status': str(qb_stats.overall_status)}

        consent = latest_consent(user=patient)
        if consent:
            row['consent'] = FHIR_datetime.as_fhir(consent.acceptance_date)

        study_id = patient.external_study_id
        if study_id:
            row['study_id'] = study_id

        current = qb_stats.current_qbd()
        previous = qb_stats.prev_qbd
        if current:
            row['visit'] = visit_name(current)
        elif previous and qb_stats.overall_status == OverallStatus.expired:
            # It's the previous visit that expired, not the current
            row['visit'] = visit_name(previous)
        results.append(row)

    return jsonify(bundle_results(elements=results))
