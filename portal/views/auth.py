"""Auth related view functions"""
import requests
from flask import Blueprint, jsonify, redirect, current_app
from flask import render_template, request, session
from flask.ext.login import login_user, logout_user
from flask.ext.user import roles_required
from werkzeug.security import gen_salt

from ..models.auth import AuthProvider, Client
from ..models.user import current_user, User, Role, UserRoles
from ..extensions import db, fa, oauth

auth = Blueprint('auth', __name__)


@auth.route('/login')
@fa.login('fb')
def login():
    """login view function

    After successful authorization at OAuth server, control
    returns here.  The user's ID and the remote oauth bearer
    token are retained in the session for subsequent use.

    """
    user = current_user()
    if user:
        return redirect('/')
    if fa.result:
        if fa.result.error:
            current_app.logger.error(fa.result.error.message)
            return fa.result.error.message
        elif fa.result.user:
            current_app.logger.debug("Successful FB login")
            if not (fa.result.user.name and fa.result.user.id):
                fa.result.user.update()
                # Grab the profile image as well
                url = '?'.join(("https://graph.facebook.com/{0}/picture",
                    "redirect=false")).format(fa.result.user.id)
                response = fa.result.provider.access(url)
                if response.status == 200:
                    image_url = response.data['data']['url']
                else:
                    image_url = None
            # Success - add or pull this user to/from database
            ap = AuthProvider.query.filter_by(provider='facebook',
                    provider_id=fa.result.user.id).first()
            if ap:
                current_app.logger.debug("Login existing user.id %d",
		    ap.user_id)
                user = User.query.filter_by(id=ap.user_id).first()
                if image_url and not user.image_url:
                    user.image_url = image_url
                    db.session.add(user)
                    db.session.commit()
            else:
                # Looks like first valid login from this auth provider
                # generate what we know and redirect to get the rest
                user = User(username=fa.result.user.name,
                        first_name=fa.result.user.first_name,
                        last_name=fa.result.user.last_name,
                        birthdate=fa.result.user.birth_date,
                        gender=fa.result.user.gender,
                        email=fa.result.user.email,
                        image_url=image_url)
                db.session.add(user)
                db.session.commit()
                current_app.logger.debug("Login new user.id %d",
		    user.id)
                ap = AuthProvider(provider='facebook',
                        provider_id=fa.result.user.id,
                        user_id=user.id)
                db.session.add(ap)
                patient = Role.query.filter_by(name='patient').first()
                default_role = UserRoles(user_id=user.id,
                        role_id=patient.id)
                db.session.add(default_role)
                db.session.commit()
            session['id'] = user.id
            session['remote_token'] = fa.result.provider.credentials.token
            login_user(user)
            return redirect('/')
    else:
        return fa.response


@auth.route('/logout')
def logout():
    """logout view function

    Logs user out by requesting the previously granted permission to
    use authenticated resources be deleted from the OAuth server, and
    clearing the browser session.

    """
    ap = AuthProvider.query.filter_by(provider='facebook',
            user_id=session['id']).first()
    headers = {'Authorization':
            'Bearer {0}'.format(session['remote_token'])}
    url = "https://graph.facebook.com/{0}/permissions".\
        format(ap.provider_id)
    requests.delete(url, headers=headers)
    current_app.logger.debug("Logout user.id %d", session['id'])
    logout_user()
    session.clear()
    return redirect('/')


@auth.route('/client', methods=('GET', 'POST'))
@roles_required('admin')
def client():
    """client view function

    For interventions wanting to be OAuth clients to the portal
    (acting as the OAuth server), they must first register with
    the portal, and provide one or more redirect URIs used during
    the OAuth authentication process.

    returns a client_id and client_secret for intervention's
    OAuth client configuration

    """
    user = current_user()
    if request.method == 'GET':
        return render_template('register_client.html')
    redirect_uri = request.form.get('redirect_uri', None)
    item = Client(
        client_id=gen_salt(40),
        client_secret=gen_salt(50),
        _redirect_uris=redirect_uri,
        _default_scopes='email',
        user_id=user.id,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(
        client_id=item.client_id,
        client_secret=item.client_secret,
        redirect_uris=item._redirect_uris
    )


@auth.route('/oauth/errors', methods=['GET', 'POST'])
def oauth_errors():
    """Called in the event of an error during the oauth dance"""
    current_app.logger.error(request.args.get('error'))
    return jsonify(error=request.args.get('error'))


@auth.route('/oauth/token', methods=['GET', 'POST'])
@oauth.token_handler
def access_token():
    """Part of the oauth dance between intervention and portal"""
    return None


@auth.route('/oauth/authorize', methods=['GET', 'POST'])
@oauth.authorize_handler
def authorize(*args, **kwargs):
    """Part of the oauth dance between intervention and portal

    Returns true, thus authorizing the client, IFF the user
    is authenticated as a portal user.  Otherwise, redirects
    to the portal root.

    """
    user = current_user()
    if not user:
        return redirect('/')
    # Typically an OAuth server (such as this portal) would
    # now request user confirmation before returning a valid
    # token to the client.  Intentionally skipping confirmation,
    # giving the intervention access to the portal anytime
    # there's an authorized portal user initiating this request
    # from the intervention.
    return True
