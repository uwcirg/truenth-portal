"""Patient view functions (i.e. not part of the API or auth)"""
import requests
import random
from datetime import datetime
from flask import abort, Blueprint, render_template
from flask_user import roles_required
from sqlalchemy import and_

from ..models.role import ROLE
from ..models.user import current_user, get_user
from ..models.user_consent import UserConsent
from ..models.organization import Organization, OrgTree
from ..models.app_text import app_text
from ..extensions import oauth

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
        org.users = [user for user in org.users if
                     user.has_role(ROLE.PATIENT) and
                     user.id in consented_users and
                     user.deleted_id is None]

        #todo iterate on users? here to add due_date stuff
        # FIXME kludge for random demo data
        for user in org.users:
            if not user.deleted:
                user.due_date = datetime(random.randint(2016, 2017), random.randint(1, 12), random.randint(1, 28))
                timedelta_days = user.due_date - datetime.today()
                timedelta_days = timedelta_days.days
                if timedelta_days < 0:
                    desc = 'overdue'
                elif timedelta_days < 30:
                    desc = 'due'
                else:
                    desc = 'not due'

                user.random_due_date_status = desc
                user.due_date = user.due_date.strftime('%d %b %Y')
                user.due_date = user.due_date.lstrip('0') # remove any leading 0 from day

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


@patients.route('/sessionReport/<int:user_id>/<instrument_id>')
@oauth.require_oauth()
def sessionReport(user_id, instrument_id):
    user = get_user(user_id)
    return render_template("sessionReport.html",user=user, current_user = current_user(), instrument_id=instrument_id)


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
        consent_url = app_text(ConsentATMA.name_key(organization=org))
        response = requests.get(consent_url)
        if response.json:
            consent_agreements[org.id] = {
                'organization_name': org.name,
                'asset': response.json()['asset'],
                'agreement_url': ConsentATMA.permanent_url(
                    version=response.json()['version'],
                    generic_url=consent_url)}
        else:
            consent_agreements[org.id] = {
                'asset': response.text, 'agreement_url': consent_url, 'organization_name': org.name}
    return consent_agreements
