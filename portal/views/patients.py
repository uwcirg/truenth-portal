"""Patient view functions (i.e. not part of the API or auth)"""
import requests
from datetime import datetime
from flask import abort, Blueprint, render_template
from flask_user import roles_required
from sqlalchemy import and_

from ..models.organization import OrgTree
from ..models.role import ROLE
from ..models.user import current_user, get_user
from ..models.user_consent import UserConsent
from ..models.organization import Organization, OrganizationIdentifier, OrgTree
from ..models.app_text import app_text
from ..models.app_text import AboutATMA, ConsentATMA, LegalATMA, ToU_ATMA
from ..extensions import oauth

patients = Blueprint('patients', __name__, url_prefix='/patients')

@patients.route('/')
@oauth.require_oauth()
@roles_required(ROLE.PROVIDER)
def patients_root():
    """patients view function, intended for providers

    Present the logged in provider the list of patients matching
    the providers organizations

    """
    user = current_user()
    patients_by_org = {}
    now = datetime.utcnow()
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

        patients_by_org[org.name] = [user for user in org.users if
                                     user.has_role(ROLE.PATIENT) and
                                     user.id in consented_users]

    return render_template(
        'patients_by_org.html', patients_by_org=patients_by_org,
        user=current_user(), wide_container="true")

@patients.route('/profile_create')
@oauth.require_oauth()
@roles_required(ROLE.PROVIDER)
def profile_create():
    consent_agreements = {}
    for org_id in OrgTree().all_top_level_ids():
            org = Organization.query.get(org_id)
            consent_url = app_text(ConsentATMA.name_key(organization=org))
            response = requests.get(consent_url)
            if response.json:
                consent_agreements[org.id] = {
                    'asset': response.json()['asset'],
                    'agreement_url': ConsentATMA.permanent_url(
                        version=response.json()['version'],
                        generic_url=consent_url)}
            else:
                consent_agreements[org.id] = {
                    'asset': response.text, 'agreement_url': consent_url}
    user = current_user()
    return render_template("profile_create.html", user = user, consent_agreements=consent_agreements)


@patients.route('/sessionReport/<int:user_id>/<instrument_id>')
def sessionReport(user_id, instrument_id):
    user = get_user(user_id)
    return render_template("sessionReport.html",user=user, instrument_id=instrument_id)


@patients.route('/patient_profile/<int:patient_id>')
@oauth.require_oauth()
@roles_required(ROLE.PROVIDER)
def patient_profile(patient_id):
    """individual patient view function, intended for providers"""
    user = current_user()
    user.check_role("edit", other_id=patient_id)
    patient = get_user(patient_id)
    if not patient:
        abort(404, "Patient {} Not Found".format(patient_id))

    return render_template('profile.html', user=patient,  providerPerspective="true")
