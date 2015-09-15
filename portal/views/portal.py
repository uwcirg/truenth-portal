"""Portal view functions (i.e. not part of the API or auth)"""
import pkg_resources
from flask import current_app, Blueprint, jsonify, render_template
from flask import redirect, request, session
from flask_swagger import swagger

from ..models.user import current_user
from ..extensions import oauth
from .crossdomain import crossdomain


portal = Blueprint('portal', __name__)
@portal.route('/')
def index():
    """portal root view function

    Renders portal.html with a valid user, index.html otherwise

    """
    user = current_user()
    if user:
        # now logged in, redirect if next was previously stored
        if 'next' in session and session['next']:
            next = session['next']
            session['next'] = None
            return redirect(next)
        return render_template('portal.html', user=user)

    # next is added as a query parameter when login is required 
    # store in session to survive a multi-request login process
    session['next'] = request.args.get('next', None)
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


@portal.route('/spec')
@crossdomain(origin='*')
def spec():
    """generate swagger friendly docs from code and comments

    View function to generate swagger formatted JSON for API
    documentation.  Pulls in a few high level values from the
    package data (see setup.py) and via flask-swagger, makes
    use of any yaml comment syntax found in application docstrings.

    Point Swagger-UI to this view for rendering

    """
    # pylint: disable=E1102, W0212
    pkg_info = pkg_resources.require("portal")[0]
    pkg_dict = dict([x.split(':', 1) for x in
                    pkg_info._get_metadata('PKG-INFO')])
    swag = swagger(current_app)
    swag['info']['version'] = pkg_dict['Version']
    swag['info']['title'] = pkg_dict['Summary']
    swag['info']['description'] = pkg_dict['Description']
    swag['info']['termsOfService'] = 'http://cirg.washington.edu'
    contact = {'name': "Clinical Informatics Research Group",
               'email': "mcjustin@uw.edu",
               'url': 'http://cirg.washington.edu'}
    swag['info']['contact'] = contact
    swag['schemes'] = ['http', 'https']

    return jsonify(swag)
