"""Patient view functions (i.e. not part of the API or auth)"""
from flask import abort, Blueprint, render_template, request
from flask_user import roles_required
from sqlalchemy import and_

from ..extensions import oauth
from ..models.app_text import app_text, ConsentATMA, VersionedResource
from ..models.organization import Organization, OrgTree, UserOrganization
from ..models.role import Role, ROLE
from ..models.user import User, current_user, get_user, UserRoles


patients = Blueprint('patients', __name__, url_prefix='/patients')

@patients.route('/')
@roles_required(ROLE.STAFF)
@oauth.require_oauth()
def patients_root():
    """patients view function, intended for providers

    Present the logged in provider the list of patients matching
    the providers organizations (and any decendent organizations)

    """
    user = current_user()

    request_org_list = request.args.get('org_list', None)
    # Build list of all organization ids, and their decendents, the
    # user belongs to
    org_list = set()
    OT = OrgTree()

    if request_org_list:
        #for selected filtered orgs, we also need to get the children of each, if any
        request_org_list = set(request_org_list.split(","))
        for orgId in request_org_list:
            if orgId == 0:  # None of the above doesn't count
                continue
            org_list.update(OT.here_and_below_id(orgId))
    else:
        for org in user.organizations:
            if org.id == 0:  # None of the above doesn't count
                continue
            org_list.update(OT.here_and_below_id(org.id))

    # Gather up all patients belonging to any of the orgs (and their children)
    # this (staff) user belongs to.
    patient_role_id = Role.query.filter(
        Role.name==ROLE.PATIENT).with_entities(Role.id).first()
    patients = User.query.join(UserRoles).filter(
        and_(User.id==UserRoles.user_id,
             UserRoles.role_id==patient_role_id,
             User.deleted_id==None
             )
        ).join(UserOrganization).filter(
            and_(UserOrganization.user_id==User.id,
                 UserOrganization.organization_id.in_(org_list)))

    return render_template(
        'patients_by_org.html', patients_list=patients.all(),
        user=user, org_list=org_list,
        wide_container="true")


@patients.route('/profile_create')
@roles_required(ROLE.STAFF)
@oauth.require_oauth()
def profile_create():
    consent_agreements = get_orgs_consent_agreements()
    user = current_user()
    leaf_organizations = user.leaf_organizations()
    return render_template(
        "profile_create.html", user = user,
        consent_agreements=consent_agreements, leaf_organizations=leaf_organizations)


@patients.route('/sessionReport/<int:user_id>/<instrument_id>/<authored_date>')
@oauth.require_oauth()
def sessionReport(user_id, instrument_id, authored_date):
    user = get_user(user_id)
    return render_template(
        "sessionReport.html",user=user,
        current_user=current_user(), instrument_id=instrument_id,
        authored_date=authored_date)


@patients.route('/patient_profile/<int:patient_id>')
@roles_required(ROLE.STAFF)
@oauth.require_oauth()
def patient_profile(patient_id):
    """individual patient view function, intended for providers"""
    user = current_user()
    user.check_role("edit", other_id=patient_id)
    patient = get_user(patient_id)
    if not patient:
        abort(404, "Patient {} Not Found".format(patient_id))
    consent_agreements = get_orgs_consent_agreements()

    return render_template(
        'profile.html', user=patient,
        providerPerspective="true", consent_agreements=consent_agreements)


def get_orgs_consent_agreements():
    consent_agreements = {}
    for org_id in OrgTree().all_top_level_ids():
        org = Organization.query.get(org_id)
        asset, url = VersionedResource.fetch_elements(
            app_text(ConsentATMA.name_key(organization=org)))

        consent_agreements[org.id] = {
                'organization_name': org.name,
                'asset': asset,
                'agreement_url': url}

    return consent_agreements
