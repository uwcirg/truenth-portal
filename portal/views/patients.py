"""Patient view functions (i.e. not part of the API or auth)"""
from datetime import datetime
from flask import abort, Blueprint, render_template
from flask_user import roles_required
from sqlalchemy import and_

from ..extensions import oauth
from ..models.app_text import app_text, ConsentATMA, VersionedResource
from ..models.fhir import assessment_status
from ..models.organization import Organization, OrgTree
from ..models.role import ROLE
from ..models.user import User, current_user, get_user
from ..models.user_consent import UserConsent


patients = Blueprint('patients', __name__, url_prefix='/patients')

@patients.route('/')
@roles_required(ROLE.PROVIDER)
@oauth.require_oauth()
def patients_root():
    """patients view function, intended for providers

    Present the logged in provider the list of patients matching
    the providers organizations

    """
    user = current_user()
    org_list_by_parent = {}
    now = datetime.utcnow()

    for org_id in OrgTree().all_top_level_ids():
        org_list_by_parent[org_id] = []

    for org in user.organizations:
        if org.id == 0:  # None of the above doesn't count
            continue
        # we require a consent agreement between the user and the
        # respective 'top-level' organization
        top_level_id = OrgTree().find(org.id).top_level()
        consent_query = UserConsent.query.filter(and_(
            UserConsent.organization_id == top_level_id,
            UserConsent.deleted_id == None,
            UserConsent.expires > now)).with_entities(UserConsent.user_id)
        consented_users = [u[0] for u in consent_query]
        #top org should have all users from its child orgs
        if org.id == top_level_id:
            user_query = User.query.filter(User.id.in_(consented_users)).all()
            org.users = [user for user in user_query if
                     user.has_role(ROLE.PATIENT) and user.deleted_id is None]
        else:
            org.users = [user for user in org.users if
                     user.has_role(ROLE.PATIENT) and
                     user.id in consented_users and
                     user.deleted_id is None]

        for user in org.users:
            user.assessment_status = assessment_status(user)

        #store patients by org into top level org list so we can list them by top-level org
        #before we were sorting by org only
        org_list_by_parent[top_level_id].append(org)
    return render_template(
        'patients_by_org.html', org_list_by_parent = org_list_by_parent, wide_container="true")


@patients.route('/profile_create')
@roles_required(ROLE.PROVIDER)
@oauth.require_oauth()
def profile_create():
    consent_agreements = get_orgs_consent_agreements()
    user = current_user()
    return render_template("profile_create.html", user = user, consent_agreements=consent_agreements)


@patients.route('/sessionReport/<int:user_id>/<instrument_id>/<authored_date>')
@oauth.require_oauth()
def sessionReport(user_id, instrument_id, authored_date):
    user = get_user(user_id)
    return render_template("sessionReport.html",user=user, current_user = current_user(), instrument_id=instrument_id, authored_date=authored_date)


@patients.route('/patient_profile/<int:patient_id>')
@roles_required(ROLE.PROVIDER)
@oauth.require_oauth()
def patient_profile(patient_id):
    """individual patient view function, intended for providers"""
    user = current_user()
    user.check_role("edit", other_id=patient_id)
    patient = get_user(patient_id)
    if not patient:
        abort(404, "Patient {} Not Found".format(patient_id))
    consent_agreements = get_orgs_consent_agreements()

    return render_template('profile.html', user=patient,  providerPerspective="true", consent_agreements = consent_agreements)


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
