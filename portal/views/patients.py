"""Patient view functions (i.e. not part of the API or auth)"""
import json
from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
)
from flask_babel import gettext as _
from flask_user import roles_required
from sqlalchemy import asc, desc

from ..extensions import oauth
from ..models.coding import Coding
from ..models.intervention import Intervention
from ..models.organization import Organization, OrgTree
from ..models.patient_list import PatientList
from ..models.questionnaire_bank import translate_visit_name
from ..models.qb_status import patient_research_study_status
from ..models.role import ROLE
from ..models.research_study import EMPRO_RS_ID, ResearchStudy
from ..models.table_preference import TablePreference
from ..models.user import current_user, get_user


patients = Blueprint('patients', __name__, url_prefix='/patients')


def users_table_pref_from_research_study_id(user, research_study_id):
    """Returns user's table preferences for given research_study id"""
    if research_study_id == 0:
        table_name = 'patientList'
    elif research_study_id == 1:
        table_name = 'substudyPatientList'
    else:
        raise ValueError('Invalid research_study_id')

    return TablePreference.query.filter_by(
        table_name=table_name, user_id=user.id).first()


def org_preference_filter(user, research_study_id):
    """Obtain user's preference for filtering organizations

    :returns: list of org IDs to use as filter, or None
    """
    pref = users_table_pref_from_research_study_id(
        user=user, research_study_id=research_study_id)
    if pref and pref.filters:
        return pref.filters.get('orgs_filter_control')


def preference_filter(user, research_study_id, arg_filter):
    """Obtain user's preference for filtering

    Looks first in request args, defaults to table preferences if not found

    :param user: current user
    :param research_study_id: 0 or 1, i.e. EMPRO_STUDY_ID
    :param arg_filter: value of request.args.get("filter")

    returns: dictionary of key/value pairs for filtering
    """
    # if arg_filter is defined, use as return value
    if arg_filter:
        # Convert from query string to dict
        filters = json.loads(arg_filter)
        return filters

    # otherwise, check db for filters from previous requests
    pref = users_table_pref_from_research_study_id(
        user=user, research_study_id=research_study_id)
    if pref and pref.filters:
        # return all but orgs and column selections
        return {
            k: v for k, v in pref.filters.items()
            if k not in ['orgs_filter_control', 'column_selections']}


def preference_sort(user, research_study_id, arg_sort, arg_order):
    """Obtain user's preference for sorting

    Looks first in request args, defaults to table preferences if not found

    :param user: current user
    :param research_study_id: 0 or 1, i.e. EMPRO_STUDY_ID
    :param arg_sort: value of request.args.get("sort")
    :param arg_sort: value of request.args.get("order")

    returns: tuple: (sort_field, sort_order)
    """
    # if args are defined, use as return value
    if arg_sort and arg_order:
        return arg_sort, arg_order

    # otherwise, check db for filters from previous requests
    pref = users_table_pref_from_research_study_id(
        user=user, research_study_id=research_study_id)
    if not pref:
        return "userid", "asc"  # reasonable defaults
    return pref.sort_field, pref.sort_order


def filter_query(query, filter_field, filter_value):
    """Extend patient list query with requested filter/search"""
    if not hasattr(PatientList, filter_field):
        # these should never get passed, but it has happened in test.
        # ignore requests to filter by unknown column
        return query

    if filter_field in ('birthdate', 'consentdate', 'empro_consentdate'):
        # these are not filterable (partial strings on date complexity) - ignore such a request
        return query

    if filter_field == 'userid':
        query = query.filter(PatientList.userid == int(filter_value))
        return query

    if filter_field in ('questionnaire_status', 'empro_status', 'action_state'):
        query = query.filter(getattr(PatientList, filter_field) == filter_value)

    pattern = f"%{filter_value.lower()}%"
    query = query.filter(getattr(PatientList, filter_field).ilike(pattern))
    return query


def sort_query(query, sort_column, direction):
    """Extend patient list query with requested sorting criteria"""
    sort_method = asc if direction == 'asc' else desc

    if not hasattr(PatientList, sort_column):
        # these should never get passed, but it has happened in test.
        # ignore requests to sort by unknown column
        return query
    query = query.order_by(sort_method(getattr(PatientList, sort_column)))
    return query


@patients.route("/page", methods=["GET"])
@roles_required([
    ROLE.INTERVENTION_STAFF.value,
    ROLE.STAFF.value,
    ROLE.STAFF_ADMIN.value])
@oauth.require_oauth()
def page_of_patients():
    """called via ajax from the patient list, deliver next page worth of patients

    Following query string parameters are expected:
    :param search: search string,
    :param sort: column to sort by,
    :param order: direction to apply to sorted column,
    :param offset: offset from first page of the given search params
    :param limit: count in a page
    :param research_study_id: default 0, set to 1 for EMPRO

    """
    def requested_orgs(user, research_study_id):
        """Return set of requested orgs limited to those the user is allowed to view"""
        # start with set of org ids the user has permission to view
        viewable_orgs = set()
        for org in user.organizations:
            ids = OrgTree().here_and_below_id(org.id)
            viewable_orgs.update(ids)

        # Reduce viewable orgs by filter preferences
        filtered_orgs = org_preference_filter(user=user, research_study_id=research_study_id)
        if filtered_orgs:
            viewable_orgs = viewable_orgs.intersection(filtered_orgs)
        return viewable_orgs

    user = current_user()
    research_study_id = int(request.args.get("research_study_id", 0))
    # due to potentially translated content, need to capture all potential values to sort
    # (not just the current page) for the front-end options list
    options = []
    if research_study_id == EMPRO_RS_ID:
        distinct_status = PatientList.query.distinct(PatientList.empro_status).with_entities(
            PatientList.empro_status)
        options.append({"empro_status": [(status[0], _(status[0])) for status in distinct_status]})
        distinct_action = PatientList.query.distinct(PatientList.action_state).with_entities(
            PatientList.action_state)
        options.append({"action_state": [(state[0], _(state[0])) for state in distinct_action]})
        distinct_visits = PatientList.query.distinct(PatientList.empro_visit).with_entities(
            PatientList.empro_visit)
        options.append({"empro_visit": [(visit[0], translate_visit_name(visit[0])) for visit in distinct_visits]})
    else:
        distinct_status = PatientList.query.distinct(
            PatientList.questionnaire_status).with_entities(PatientList.questionnaire_status)
        options.append(
            {"questionnaire_status": [(status[0], _(status[0])) for status in distinct_status]})
        distinct_visits = PatientList.query.distinct(PatientList.visit).with_entities(
            PatientList.visit)
        options.append({"visit": [(visit[0], translate_visit_name(visit[0])) for visit in distinct_visits]})

    viewable_orgs = requested_orgs(user, research_study_id)
    query = PatientList.query.filter(PatientList.org_id.in_(viewable_orgs))
    if research_study_id == EMPRO_RS_ID:
        # only include those in the study.  use empro_consentdate as a quick check
        query = query.filter(PatientList.empro_consentdate.isnot(None))
    if not request.args.get('include_test_role', "false").lower() == "true":
        query = query.filter(PatientList.test_role.is_(False))

    filters = preference_filter(
        user=user, research_study_id=research_study_id, arg_filter=request.args.get("filter"))
    if filters:
        for key, value in filters.items():
            query = filter_query(query, key, value)

    sort_column, sort_order = preference_sort(
        user=user, research_study_id=research_study_id, arg_sort=request.args.get("sort"),
        arg_order=request.args.get("order"))
    query = sort_query(query, sort_column, sort_order)

    total = query.count()
    query = query.offset(request.args.get('offset', 0))
    query = query.limit(request.args.get('limit', 10))

    # Returns structured JSON with totals and rows
    data = {"total": total, "totalNotFiltered": total, "rows": [], "options": options}
    for row in query:
        data['rows'].append({
            "userid": row.userid,
            "firstname": row.firstname,
            "lastname": row.lastname,
            "birthdate": row.birthdate,
            "email": row.email,
            "questionnaire_status": _(row.questionnaire_status),
            "empro_status": _(row.empro_status),
            "action_state": _(row.action_state),
            "visit": translate_visit_name(row.visit),
            "empro_visit": translate_visit_name(row.empro_visit),
            "study_id": row.study_id,
            "consentdate": row.consentdate,
            "empro_consentdate": row.empro_consentdate,
            "clinician": row.clinician,
            "org_id": row.org_id,
            "org_name": row.org_name,
            "deleted": row.deleted,
            "test_role": row.test_role,
        })
    return jsonify(data)


@patients.route('/', methods=('GET', 'POST'))
@roles_required([
    ROLE.INTERVENTION_STAFF.value,
    ROLE.STAFF.value,
    ROLE.STAFF_ADMIN.value])
@oauth.require_oauth()
def patients_root():
    """creates patients list dependent on user role

    :param reset_cache: (as query parameter).  If present, the cached
     as_of_date key used in assessment status lookup will be reset to
     current (forcing a refresh)

    The returned list of patients depends on the users role:
      admin users: all non-deleted patients
      clinicians: all patients in the sub-study with common consented orgs
      intervention-staff: all patients with common user_intervention
      staff, staff_admin: all patients with common consented organizations

    NB: a single user with both staff and intervention-staff is not
    expected and will raise a 400: Bad Request

    """
    user = current_user()
    return render_template(
        'admin/patients_by_org.html', user=user,
        wide_container="true",
    )


@patients.route('/substudy', methods=('GET', 'POST'))
@roles_required([
    ROLE.CLINICIAN.value,
    ROLE.STAFF.value,
    ROLE.STAFF_ADMIN.value])
@oauth.require_oauth()
def patients_substudy():
    """substudy patients list dependent on user role

    :param reset_cache: (as query parameter).  If present, the cached
     as_of_date key used in assessment status lookup will be reset to
     current (forcing a refresh)

    The returned list of patients depends on the users role:
      clinicians: all patients in the sub-study with common consented orgs
      staff, staff_admin: all patients with common consented organizations

    """
    user = current_user()
    return render_template(
        'admin/patients_substudy.html', user=user,
        wide_container="true",
    )


@patients.route('/patient-profile-create')
@roles_required([ROLE.STAFF_ADMIN.value, ROLE.STAFF.value])
@oauth.require_oauth()
def patient_profile_create():
    user = current_user()
    consent_agreements = Organization.consent_agreements(
        locale_code=user.locale_code)
    return render_template(
        "profile/patient_profile_create.html", user=user,
        consent_agreements=consent_agreements)


@patients.route(
    '/session-report/<int:subject_id>/<instrument_id>/<authored_date>')
@oauth.require_oauth()
def session_report(subject_id, instrument_id, authored_date):
    user = get_user(subject_id, 'view')
    return render_template(
        "sessionReport.html", user=user,
        current_user=current_user(), instrument_id=instrument_id,
        authored_date=authored_date)


@patients.route(
    '/<int:subject_id>/longitudinal-report/<instrument_id>')
@oauth.require_oauth()
def longitudinal_report(subject_id, instrument_id):
    user = get_user(subject_id, 'view')
    enrolled_in_substudy = EMPRO_RS_ID in ResearchStudy.assigned_to(user)
    return render_template(
        "longitudinalReport.html", user=user,
        enrolled_in_substudy=enrolled_in_substudy,
        instrument_id=instrument_id, current_user=current_user())


@patients.route('/patient_profile/<int:patient_id>')
@roles_required([
    ROLE.CLINICIAN.value,
    ROLE.STAFF_ADMIN.value,
    ROLE.STAFF.value,
    ROLE.INTERVENTION_STAFF.value])
@oauth.require_oauth()
def patient_profile(patient_id):
    """individual patient view function, intended for staff"""
    user = current_user()
    patient = get_user(patient_id, 'edit')
    consent_agreements = Organization.consent_agreements(
        locale_code=user.locale_code)

    user_interventions = []
    interventions = Intervention.query.order_by(
        Intervention.display_rank).all()
    for intervention in interventions:
        display = intervention.display_for_user(patient)
        if (display.access and display.link_url is not None and
                display.link_label is not None):
            user_interventions.append({"name": intervention.name})
    research_study_status = patient_research_study_status(patient)
    enrolled_in_substudy = EMPRO_RS_ID in research_study_status

    return render_template(
        'profile/patient_profile.html', user=patient,
        current_user=user,
        enrolled_in_substudy=enrolled_in_substudy,
        consent_agreements=consent_agreements,
        user_interventions=user_interventions)


@patients.route('/treatment-options')
@oauth.require_oauth()
def treatment_options():
    code_list = current_app.config.get('TREATMENT_OPTIONS')
    if code_list:
        treatment_options = []
        for item in code_list:
            code, system = item
            treatment_options.append({
                "code": code,
                "system": system,
                "text": Coding.display_lookup(code, system)
            })
    else:
        abort(400, "Treatment options are not available.")
    return jsonify(treatment_options=treatment_options)
