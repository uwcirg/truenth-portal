"""Patient view functions (i.e. not part of the API or auth)"""
from datetime import datetime

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
from sqlalchemy import and_

from ..extensions import oauth
from ..models.coding import Coding
from ..models.intervention import Intervention, UserIntervention
from ..models.organization import Organization, OrgTree
from ..models.qb_timeline import qb_status_visit_name, QB_StatusCacheKey
from ..models.role import ROLE
from ..models.table_preference import TablePreference
from ..models.user import (
    User,
    active_patients,
    current_user,
    get_user_or_abort,
)
from ..models.user_consent import UserConsent
from ..type_tools import check_int

patients = Blueprint('patients', __name__, url_prefix='/patients')


@patients.route('/', methods=('GET', 'POST'))
@roles_required([ROLE.STAFF.value, ROLE.INTERVENTION_STAFF.value])
@oauth.require_oauth()
def patients_root():
    """creates patients list dependent on user role

    :param reset_cache: (as query parameter).  If present, the cached
     as_of_date key used in assessment status lookup will be reset to
     current (forcing a refresh)

    The returned list of patients depends on the users role:
      admin users: all non-deleted patients
      intervention-staff: all patients with common user_intervention
      staff: all patients with common consented organizations

    NB: a single user with both staff and intervention-staff is not
    expected and will raise a 400: Bad Request

    """
    broken_role_situation = (
        "Patients list for staff and intervention-staff are mutually"
        " exclusive - user shouldn't have both roles")

    def org_restriction(user):
        """Determine if user (prefs) restrict list of patients by org

        :returns: None if no org restrictions apply, or a list of org_ids

        """
        if user.has_role(ROLE.ADMIN.value):
            return None  # no restrictions

        org_list = set()
        if user.has_role(ROLE.STAFF.value):
            if user.has_role(ROLE.INTERVENTION_STAFF.value):
                abort(400, broken_role_situation)
            pref_org_list = None
            # check user table preference for organization filters
            pref = TablePreference.query.filter_by(
                table_name='patientList', user_id=user.id).first()
            if pref and pref.filters:
                pref_org_list = pref.filters.get('orgs_filter_control')

            # Build list of all organization ids, and their descendants, the
            # user belongs to
            ot = OrgTree()

            if pref_org_list:
                # for preferred filtered orgs
                pref_org_list = set(pref_org_list)
                for orgId in pref_org_list:
                    check_int(orgId)
                    if orgId == 0:  # None of the above doesn't count
                        continue
                    for org in user.organizations:
                        if int(orgId) in ot.here_and_below_id(org.id):
                            org_list.add(orgId)
                            break
            else:
                for org in user.organizations:
                    if org.id == 0:  # None of the above doesn't count
                        continue
                    org_list.update(ot.here_and_below_id(org.id))
            return list(org_list)

    def intervention_restrictions(user):
        """returns tuple of lists for interventions: (disallow, require)

        Users may not have access to some interventions (such as randomized
        control trials).  In such a case, the first of the tuple items
        will name intervention ids which should not be included.

        Other users get access to all patients with one or more
        interventions.  In this case, a list of interventions for which
        the user should be granted access is in the second position.

        """
        if user.has_role(ROLE.ADMIN.value):
            return None, None  # no restrictions

        disallowed, required = None, None
        if user.has_role(ROLE.STAFF.value):
            if user.has_role(ROLE.INTERVENTION_STAFF.value):
                abort(400, broken_role_situation)
            # staff users aren't to see patients from RCT interventions
            disallowed = Intervention.rct_ids()
        if user.has_role(ROLE.INTERVENTION_STAFF.value):
            # Look up associated interventions
            uis = UserIntervention.query.filter(
                UserIntervention.user_id == user.id)
            # check if the user is associated with any intervention at all
            if uis.count() == 0:
                abort(400, "User is not associated with any intervention.")
            required = [ui.intervention_id for ui in uis]
        return disallowed, required

    if request.form.get('reset_cache'):
        QB_StatusCacheKey().update(datetime.utcnow())

    user = current_user()
    # Not including test accounts by default, unless requested
    include_test_roles = request.args.get('include_test_roles')
    consent_query = UserConsent.query.filter(and_(
        UserConsent.deleted_id.is_(None),
        UserConsent.expires > datetime.utcnow()))
    consented_users = [u.user_id for u in consent_query if u.staff_editable]
    disallowed_iv_ids, required_iv_ids = intervention_restrictions(user)
    patients = active_patients(
        require_orgs=org_restriction(user),
        include_test_role=include_test_roles,
        include_deleted=True,
        require_interventions=required_iv_ids,
        disallow_interventions=disallowed_iv_ids,
        filter_by_ids=consented_users)

    # get assessment status only if it is needed as specified by config
    qb_status_cache_age = 0
    if 'status' in current_app.config.get('PATIENT_LIST_ADDL_FIELDS'):
        status_cache_key = QB_StatusCacheKey()
        cached_as_of_key = status_cache_key.current()
        qb_status_cache_age = status_cache_key.minutes_old()
        patient_list = []
        for patient in patients:
            if patient.deleted:
                patient_list.append(patient)
                continue
            a_s, visit = qb_status_visit_name(patient.id, cached_as_of_key)
            patient.assessment_status = _(a_s)
            patient.current_qb = visit
            patient_list.append(patient)
        patients = patient_list

    return render_template(
        'admin/patients_by_org.html', patients_list=patients, user=user,
        qb_status_cache_age=qb_status_cache_age, wide_container="true",
        include_test_roles=include_test_roles)


@patients.route('/patient-profile-create')
@roles_required(ROLE.STAFF.value)
@oauth.require_oauth()
def patient_profile_create():
    user = current_user()
    consent_agreements = Organization.consent_agreements(
        locale_code=user.locale_code)
    leaf_organizations = user.leaf_organizations()
    return render_template(
        "profile/patient_profile_create.html", user=user,
        consent_agreements=consent_agreements,
        leaf_organizations=leaf_organizations)


@patients.route(
    '/session-report/<int:subject_id>/<instrument_id>/<authored_date>')
@oauth.require_oauth()
def session_report(subject_id, instrument_id, authored_date):
    current_user().check_role("view", other_id=subject_id)
    user = get_user_or_abort(subject_id)
    return render_template(
        "sessionReport.html", user=user,
        current_user=current_user(), instrument_id=instrument_id,
        authored_date=authored_date)


@patients.route('/patient_profile/<int:patient_id>')
@roles_required([ROLE.STAFF.value, ROLE.INTERVENTION_STAFF.value])
@oauth.require_oauth()
def patient_profile(patient_id):
    """individual patient view function, intended for staff"""
    user = current_user()
    user.check_role("edit", other_id=patient_id)
    patient = get_user_or_abort(patient_id)
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

    return render_template(
        'profile/patient_profile.html', user=patient,
        current_user=user,
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
