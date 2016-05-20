"""Patient view functions (i.e. not part of the API or auth)"""
from flask import Blueprint, render_template
from flask.ext.user import roles_required

from ..models.role import ROLE
from ..models.user import current_user
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
    for org in user.organizations:
        patients_by_org[org.name] = org.users

    return render_template(
        'patients_by_org.html', patients_by_org=patients_by_org)
