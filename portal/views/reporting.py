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
from flask_user import roles_required

from ..date_tools import report_format
from ..extensions import oauth
from ..models.organization import Organization, OrgTree
from ..models.qb_status import QB_Status
from ..models.research_study import BASE_RS_ID
from ..models.role import ROLE
from ..models.user import current_user, patients_query
from ..timeout_lock import LockTimeout, guarded_task_launch

reporting_api = Blueprint('reporting', __name__)


@reporting_api.route('/admin/overdue-table/<int:organization_id>')
@roles_required([ROLE.STAFF_ADMIN.value, ROLE.STAFF.value])
@oauth.require_oauth()
def overdue_table(organization_id):
    """View for staff access to generated email content

    Only for debugging & QA - scheduled jobs generate and send
    such reports at regular intervals.

    The included patients depends on current user's organization
    affiliation, including all patients at and below any level of the
    organization tree for which the current user has access, at or below
    given organization_id.

    :param organization_id: Top level organization ID to test
    :returns: html content typically sent directly to site resource

    """
    from ..models.reporting import overdue_stats_by_org
    top_org = Organization.query.get_or_404(organization_id)

    return generate_overdue_table_html(
        overdue_stats=overdue_stats_by_org(),
        user=current_user(), top_org=top_org)


@reporting_api.route('/admin/empro-overdue-table/<int:organization_id>')
@roles_required([ROLE.STAFF_ADMIN.value, ROLE.STAFF.value])
@oauth.require_oauth()
def empro_overdue_table(organization_id):
    """View for staff access to generated email content

    Only for debugging & QA - scheduled jobs generate and send
    such reports at regular intervals.

    The included patients depends on current user's organization
    affiliation, including all patients at and below any level of the
    organization tree for which the current user has access, at or below
    given organization_id.

    :param organization_id: Top level organization ID to test
    :returns: html content typically sent directly to site resource

    """
    from ..models.reporting import empro_overdue_stats
    top_org = Organization.query.get_or_404(organization_id)

    return generate_EMPRO_overdue_table_html(
        overdue_stats=empro_overdue_stats(),
        user=current_user(), top_org=top_org)


def generate_overdue_table_html(overdue_stats, user, top_org):
    """generate html from given statistics

    :param overdue_stats: a dict keyed by
     ``overdue_stats[(org_id, org_name)]``, and for each org, a list
      of overdue patient tuples, respectively containing
      ``(user.id, study_id, visit_name, due_date, expired_date)``
    :param user: the user generating the table, necessary to determine
      patient visibility
    :param top_org: used to restrict report to a portion of the patients
      for which the given user has view permissions

    :returns: report in html

    """
    ot = OrgTree()
    rows = []
    for org_id, org_name in sorted(overdue_stats, key=lambda x: x[1]):
        if top_org and not ot.at_or_below_ids(top_org.id, [org_id]):
            continue
        if not user.can_view_org(org_id):
            continue

        # For each org, generate a row with org name in position 0
        sitecode = ot.find(org_id).sitecode
        rows.append((org_name, org_id, sitecode, '', '', '', ''))

        # Prepend each patient row to line up with header
        site_spacer = ''
        od_tups = overdue_stats[(org_id, org_name)]
        for user_id, study_id, visit_name, due_date, expired_date in od_tups:
            rows.append((
                site_spacer, user_id, study_id, visit_name,
                report_format(due_date),
                report_format(expired_date)))

    return render_template(
        'site_overdue_table.html', rows=rows)


def generate_EMPRO_overdue_table_html(overdue_stats, user, top_org):
    """EMPRO specific overdue table generation.

    :param overdue_stats: a dict keyed by
     ``overdue_stats[(org_id, org_name)]``, and for each org, a list
      of overdue patient namedtuples, respectively containing an
      ``EmproOverdueRow`` instance
    :param user: the user generating the table, necessary to determine
      patient visibility
    :param top_org: the specific organization to generate a report for

    :returns: report in html

    """
    rows = []
    check = [i for i in overdue_stats if i[0] == top_org.id]
    if not check:
        raise ValueError(
            f"no patient data for organization {top_org}; EMPRO overdue"
            f" reports per leaf org, not parent."
            f" Try one of {overdue_stats.keys()}")

    org_id, org_name = [i for i in overdue_stats if i[0] == top_org.id][0]
    od_tups = overdue_stats[(org_id, org_name)]
    for row in od_tups:
        rows.append(row)

    return render_template(
        'empro_site_overdue_table.html', rows=rows, site=org_name)


@reporting_api.route('/admin/overdue-numbers')
@roles_required(
    [ROLE.ADMIN.value, ROLE.STAFF_ADMIN.value, ROLE.STAFF.value,
     ROLE.INTERVENTION_STAFF.value])
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

    research_study_id = BASE_RS_ID
    for user in patients_query(
            acting_user=current_user(), include_test_role=False):
        a_s = QB_Status(
            user,
            research_study_id=research_study_id,
            as_of_date=datetime.utcnow())
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


@reporting_api.route('/api/report/questionnaire_status/test')
@roles_required(
    [ROLE.ADMIN.value, ROLE.STAFF_ADMIN.value, ROLE.STAFF.value,
     ROLE.INTERVENTION_STAFF.value, ROLE.CLINICIAN.value])
@oauth.require_oauth()
def questionnaire_status_test():
    """Test interface to generate portion of adherence report

    See questionnaire_status() for real use.

    Include query string parameters to test list of users, etc.
    """
    from ..tasks import adherence_report_task

    # This frequently takes over a minute to produce.  Generate a serializable
    # form of all args for reliable hand off to a background task.
    kwargs = {
        'requested_as_of_date': request.args.get('as_of_date'),
        'acting_user_id': current_user().id,
        'include_test_role': request.args.get('include_test_role', False),
        'org_id': request.args.get('org_id', 146999),
        'limit': int(request.args.get('limit', 10)),
        'research_study_id': int(request.args.get('research_study_id', 0)),
        'lock_key': "adherence_report_throttle",
        'response_format': request.args.get('format', 'csv').lower()
    }

    # Hand the task off to the job queue, and return 202 with URL for
    # checking the status of the task
    try:
        task = guarded_task_launch(adherence_report_task, **kwargs)
        return jsonify({
            'task_status': url_for(
                'portal.task_status', task_id=task.id, _external=True),
            'results': url_for(
                'portal.task_result', task_id=task.id, _external=True)})
    except LockTimeout:
        msg = (
            "The system is busy exporting a report for another user. "
            "Please try again in a few minutes.")
        response = make_response(msg, 502)
        response.mimetype = "text/plain"
        return response


@reporting_api.route('/api/report/questionnaire_status')
@roles_required(
    [ROLE.ADMIN.value, ROLE.STAFF_ADMIN.value, ROLE.STAFF.value,
     ROLE.INTERVENTION_STAFF.value, ROLE.CLINICIAN.value])
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
      - name: research_study_id
        in: query
        description: research study id, defaults to 0
        required: false
        type: integer
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
        'limit': None,
        'research_study_id': int(request.args.get('research_study_id', 0)),
        'lock_key': "adherence_report_throttle",
        'response_format': request.args.get('format', 'json').lower()
    }

    # Hand the task off to the job queue, and return 202 with URL for
    # checking the status of the task
    try:
        task = guarded_task_launch(adherence_report_task, **kwargs)
        return jsonify({}), 202, {'Location': url_for(
            'portal.task_status', task_id=task.id, _external=True)}
    except LockTimeout:
        msg = (
            "The system is busy exporting a report for another user. "
            "Please try again in a few minutes.")
        response = make_response(msg, 502)
        response.mimetype = "text/plain"
        return response
