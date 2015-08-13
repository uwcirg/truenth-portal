"""Portal view functions (i.e. not part of the API or auth)"""
from flask import Blueprint, render_template

from ..models.user import current_user
from ..extensions import oauth

portal = Blueprint('portal', __name__)
@portal.route('/')
def index():
    """portal root view function

    Renders portal.html with a valid user, index.html otherwise

    """
    user = current_user()
    if user:
        return render_template('portal.html', user=user)
    return render_template('index.html')


@portal.route('/profile')
@oauth.require_oauth()
def profile():
    """profile view function"""
    return render_template('profile.html', user=current_user())


@portal.route('/terms-of-use')
def termsofuse():
    """terms of use view function"""
    return render_template('termsofuse.html')

