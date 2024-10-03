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
from ..models.qb_status import patient_research_study_status
from ..models.role import ROLE
from ..models.research_study import EMPRO_RS_ID, ResearchStudy
from ..models.table_preference import TablePreference
from ..models.user import current_user, get_user


patients = Blueprint('patients', __name__, url_prefix='/patients')


def org_preference_filter(user, research_study_id):
    """Obtain user's preference for filtering organizations

    :returns: list of org IDs to use as filter, or None

    """
    if research_study_id == 0:
        table_name = 'patientList'
    elif research_study_id == 1:
        table_name = 'substudyPatientList'
    else:
        raise ValueError('Invalid research_study_id')

    # check user table preference for organization filters
    pref = TablePreference.query.filter_by(
        table_name=table_name, user_id=user.id).first()
    if pref and pref.filters:
        return pref.filters.get('orgs_filter_control')
    return None


def render_patients_list(
        request, research_study_id, template_name):
    user = current_user()
    return render_template(
            template_name, user=user,
            wide_container="true",
        )


def filter_query(query, filter_field, filter_value):
    """Extend patient list query with requested filter/search"""
    pattern = f"%{filter_value.lower()}%"
    if filter_field == 'firstname':
        query = query.filter(PatientList.first_name.ilike(pattern))
    if filter_field == 'lastname':
        query = query.filter(PatientList.last_name.ilike(pattern))
    if filter_field == 'email':
        query = query.filter(PatientList.email.ilike(pattern))
    if filter_field == 'study_id':
        query = query.filter(PatientList.study_id.ilike(pattern))
    if filter_field == 'visit':
        query = query.filter(PatientList.visit.ilike(pattern))
    if filter_field == 'questionnaire_status':
        query = query.filter(PatientList.questionnaire_status == filter_value)
    if filter_field == 'userid':
        query = query.filter(PatientList.id == int(filter_value))
    return query


def sort_query(query, sort_column, direction):
    """Extend patient list query with requested sorting criteria"""
    sort_method = asc if direction == 'asc' else desc

    if sort_column == 'firstname':
        query = query.order_by(sort_method(PatientList.first_name))
    if sort_column == 'lastname':
        query = query.order_by(sort_method(PatientList.last_name))
    if sort_column == 'email':
        query = query.order_by(sort_method(PatientList.email))
    if sort_column == 'study_id':
        query = query.order_by(sort_method(PatientList.study_id))
    if sort_column == 'visit':
        query = query.order_by(sort_method(PatientList.visit))
    if sort_column == 'questionnaire_status':
        query = query.order_by(sort_method(PatientList.questionnaire_status))
    if sort_column == 'userid':
        query = query.order_by(sort_method(PatientList.id))
    if sort_column == 'org_name':
        query = query.order_by(sort_method(PatientList.sites))
    if sort_column == 'birthdate':
        query = query.order_by(sort_method(PatientList.birthdate))
    if sort_column == 'consentdate':
        query = query.order_by(sort_method(PatientList.consent_date))
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
    user = current_user()
    # build set of org ids the user has permission to view
    viewable_orgs = set()
    for org in user.organizations:
        ids = OrgTree().here_and_below_id(org.id)
        viewable_orgs.update(ids)

    research_study_id = int(request.args.get("research_study_id", 0))
    # Reduce viewable orgs by filter preferences
    filtered_orgs = org_preference_filter(user=user, research_study_id=research_study_id)
    if filtered_orgs:
        viewable_orgs = viewable_orgs.intersection(filtered_orgs)

    query = PatientList.query.filter(PatientList.org_id.in_(viewable_orgs))
    if not request.args.get('include_test_role', "false").lower() == "true":
        query = query.filter(PatientList.test_role.is_(False))
    if "filter" in request.args:
        filters = json.loads(request.args.get("filter"))
        for key, value in filters.items():
            query = filter_query(query, key, value)

    sort_column = request.args.get("sort", "userid")
    sort_order = request.args.get("order", "asc")
    query = sort_query(query, sort_column, sort_order)

    total = query.count()
    query = query.offset(request.args.get('offset', 0))
    query = query.limit(request.args.get('limit', 10))

    # Returns JSON structured as:
    # { "total": int, "totalNotFiltered": int, "rows": [
    #   { "id": int, "column": value},
    #   { "id": int, "column": value},
    # ]}
    data = {"total": total, "totalNotFiltered": total, "rows": []}
    for row in query:
        data['rows'].append({
            "userid": row.id,
            "firstname": row.first_name,
            "lastname": row.last_name,
            "birthdate": row.birthdate,
            "email": row.email,
            "questionnaire_status": _(row.questionnaire_status),
            "visit": row.visit,
            "study_id": row.study_id,
            "consentdate": row.consent_date,
            "org_id": row.org_id,
            "org_name": row.sites,
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
    return render_patients_list(
        request,
        research_study_id=0,
        template_name='admin/patients_by_org.html')


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
    return render_patients_list(
        request,
        research_study_id=EMPRO_RS_ID,
        template_name='admin/patients_substudy.html')


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
