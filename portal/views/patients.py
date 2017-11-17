"""Patient view functions (i.e. not part of the API or auth)"""
from flask import abort, Blueprint, jsonify, render_template, request
from flask import current_app, url_for
from flask_user import roles_required
from sqlalchemy import and_

from ..extensions import oauth
from ..models.app_text import MailResource, UserInviteEmail_ATMA
from ..models.assessment_status import overall_assessment_status
from ..models.communication import load_template_args
from ..models.fhir import Coding
from ..models.intervention import Intervention, UserIntervention
from ..models.organization import Organization, OrgTree, UserOrganization
from ..models.questionnaire_bank import QuestionnaireBank, visit_name
from ..models.role import Role, ROLE
from ..models.table_preference import TablePreference
from ..models.user import User, current_user, get_user, UserRoles
from ..models.user_consent import UserConsent
from ..models.app_text import app_text, InitialConsent_ATMA, VersionedResource
from .portal import check_int
from datetime import datetime


patients = Blueprint('patients', __name__, url_prefix='/patients')

@patients.route('/')
@roles_required([ROLE.STAFF, ROLE.INTERVENTION_STAFF])
@oauth.require_oauth()
def patients_root():
    """patients view function, intended for staff

    Present the logged in staff the list of patients matching
    the staff's organizations (and any decendent organizations)

    """
    user = current_user()

    patient_role_id = Role.query.filter(
        Role.name==ROLE.PATIENT).with_entities(Role.id).first()

    # empty patient query list to start, unionize with other relevant lists
    patients = User.query.filter(User.id==-1)

    org_list = set()

    now = datetime.utcnow()
    consented_users = []

    consent_query = UserConsent.query.filter(and_(
                         UserConsent.deleted_id.is_(None),
                         UserConsent.expires > now)).with_entities(
                             UserConsent.user_id)
    consented_users = [u.user_id for u in consent_query]

    if user.has_role(ROLE.STAFF):
        pref_org_list = None
        # check user table preference for organization filters
        pref = TablePreference.query.filter_by(table_name='patientList',
                                               user_id=user.id).first()
        if pref and pref.filters:
            pref_org_list = pref.filters.get('orgs_filter_control')

        # Build list of all organization ids, and their decendents, the
        # user belongs to
        OT = OrgTree()

        if pref_org_list:
            # for preferred filtered orgs
            pref_org_list = set(pref_org_list.split(","))
            for orgId in pref_org_list:
                check_int(orgId)
                if orgId == 0:  # None of the above doesn't count
                    continue
                for org in user.organizations:
                    if int(orgId) in OT.here_and_below_id(org.id):
                        org_list.add(orgId)
                        break
        else:
            for org in user.organizations:
                if org.id == 0:  # None of the above doesn't count
                    continue
                org_list.update(OT.here_and_below_id(org.id))

        # Gather up all patients belonging to any of the orgs (and their
        # children) this (staff) user belongs to.
        org_patients = User.query.join(UserRoles).filter(
            and_(User.id==UserRoles.user_id,
                 UserRoles.role_id==patient_role_id,
                 User.deleted_id.is_(None),
                 User.id.in_(consented_users)
                 )
            ).join(UserOrganization).filter(
                and_(UserOrganization.user_id==User.id,
                     UserOrganization.organization_id != 0,
                     UserOrganization.organization_id.in_(org_list)))
        patients = patients.union(org_patients)

    if user.has_role(ROLE.INTERVENTION_STAFF):
        uis = UserIntervention.query.filter(UserIntervention.user_id == user.id)
        ui_list = [ui.intervention_id for ui in uis]

        # Gather up all patients belonging to any of the interventions
        # this intervention_staff user belongs to
        ui_patients = User.query.join(UserRoles).filter(
            and_(User.id==UserRoles.user_id,
                 UserRoles.role_id==patient_role_id,
                 User.deleted_id.is_(None),
                 User.id.in_(consented_users))
                 ).join(UserIntervention).filter(
                 and_(UserIntervention.user_id==User.id,
                     UserIntervention.intervention_id.in_(ui_list)))
        patients = patients.union(ui_patients)

    # get assessment status only if it is needed as specified by config
    if 'status' in current_app.config.get('PATIENT_LIST_ADDL_FIELDS'):
        patient_list = []
        for patient in patients:
            a_s, qbd = overall_assessment_status(patient.id)
            patient.assessment_status = a_s
            patient.current_qb = visit_name(qbd)
            patient_list.append(patient)
        patients = patient_list

    return render_template(
        'patients_by_org.html', patients_list=patients,
        user=user, org_list=org_list,
        wide_container="true")

@patients.route('/patient-profile-create')
@roles_required(ROLE.STAFF)
@oauth.require_oauth()
def patient_profile_create():
    consent_agreements = Organization.consent_agreements()
    user = current_user()
    leaf_organizations = user.leaf_organizations()
    return render_template(
        "patient_profile_create.html", user = user,
        consent_agreements=consent_agreements,
        leaf_organizations=leaf_organizations)


@patients.route('/sessionReport/<int:user_id>/<instrument_id>/<authored_date>')
@oauth.require_oauth()
def sessionReport(user_id, instrument_id, authored_date):
    user = get_user(user_id)
    return render_template(
        "sessionReport.html",user=user,
        current_user=current_user(), instrument_id=instrument_id,
        authored_date=authored_date)


@patients.route('/patient_profile/<int:patient_id>')
@roles_required([ROLE.STAFF, ROLE.INTERVENTION_STAFF])
@oauth.require_oauth()
def patient_profile(patient_id):
    """individual patient view function, intended for staff"""
    user = current_user()
    user.check_role("edit", other_id=patient_id)
    patient = get_user(patient_id)
    if not patient:
        abort(404, "Patient {} Not Found".format(patient_id))
    consent_agreements = Organization.consent_agreements()

    user_interventions = []
    interventions =\
            Intervention.query.order_by(Intervention.display_rank).all()
    for intervention in interventions:
        display = intervention.display_for_user(patient)
        if (display.access and display.link_url is not None and
            display.link_label is not None):
            user_interventions.append({"name": intervention.name})
        if intervention.name == 'assessment_engine':
            # Need to extend with subject_id as the staff user is driving
            patient.assessment_link = '{url}&subject_id={id}'.format(
                url=display.link_url, id=patient.id)

    return render_template(
        'profile.html', user=patient,
        current_user=user,
        providerPerspective="true",
        consent_agreements=consent_agreements,
        user_interventions=user_interventions)

@patients.route('/treatment-options')
@oauth.require_oauth()
def treatment_options():
    code_list = current_app.config.get('TREATMENT_OPTIONS')
    if code_list:
        treatment_options = []
        for item in code_list:
            code, system = item;
            treatment_options.append({
                "code": code,
                "system": system,
                "text": Coding.display_lookup(code, system)
            });
    else:
        abort(400, "Treatment options are not available.")
    return jsonify(treatment_options=treatment_options)
