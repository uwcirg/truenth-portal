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
    """client registration

    Central Services uses the OAuth 2.0 Authorization Code Grant flow
    (http://tools.ietf.org/html/rfc6749#section-4.1)
    to authorize all sensitive API access. As a prerequisite, any
    client (intervention) wishing to make authorized calls must first
    register at this endpoint.
    ---
    tags:
      - OAuth
    operationId: client
    parameters:
      - name: redirect_uri
        in: formData
        description:
          Redirect URIs. The service will only redirect to URIs in
          the list. All URIs must be protected with TLS security
          (i.e. https) beyond inital testing. Separate multiple
          URIs with a single whitespace character.
        required: true
        type: string
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: client_response
          required:
            - client_id
            - client_secret
          properties:
            client_id:
              type: string
              description:
                Identification unique to a Central Serivce client.
                Passed in calls to obtain an authorization token
            client_secret:
              type: string
              description:
                Safe guarded secret used by Intervention's OAuth 
                client library.

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


@auth.route('/oauth/errors', methods=('GET', 'POST'))
def oauth_errors():
    """Redirect target for oauth errors
    
    Shouldn't be called directly, this endpoint is the redirect target
    when something goes wrong during authorization code requests
    ---
    tags:
      - OAuth
    operationId: oauth_errors
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: error_response
          required:
            - error
          properties:
            error:
              type: string
              description: Known details of error situation.

    """
    current_app.logger.error(request.args.get('error'))
    return jsonify(error=request.args.get('error')), 400


@auth.route('/oauth/token', methods=('GET', 'POST'))
@oauth.token_handler
def access_token():
    """Exchange authorization code for access token
    
    OAuth client libraries must POST the authorization code obtained
    from /oauth/authorize in exchange for a Bearer Access Token.
    ---
    tags:
      - OAuth
    operationId: access_token
    parameters:
      - name: client_id
        in: formData
        description:
          Client's unique identifier, obtained during registration
        required: true
        type: string
      - name: client_secret
        in: formData
        description:
          Client's secret, obtained during registration
        required: true
        type: string
      - name: code
        in: formData
        description:
          The authorization code obtained from /oauth/authorize
        required: true
        type: string
      - name: grant_type
        in: formData
        description:
          Type of OAuth authorization requested.  Use "authorization_code"
        required: true
        type: string
      - name: redirect_uri
        in: formData
        description:
          Intervention's target URI for call back.
        required: true
        type: string
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: access_token
          required:
            - access_token
            - token_type
            - expires_in
            - refresh_token
            - scope
          properties:
            access_token:
              type: string
              description:
                The access token to include in the Authorization header
                for protected API use.
              required: true
            token_type:
              type: string
              description: Type of access token, always 'Bearer'
              required: true
            expires_in:
              type: integer
              format: int64
              description:
                Number of seconds for which the access token will
                remain valid
              required: true
            refresh_token:
              type: string
              description:
                Use to refresh an access token, in place of the
                authorizion token.
              required: true
            scope:
              type: string
              description: The authorized scope.

    """
    return None


@auth.route('/oauth/authorize', methods=('GET','POST'))
@oauth.authorize_handler
def authorize(*args, **kwargs):
    """Authorize the client to access Central Service resources
    
    For OAuth 2.0, the resource owner communicates their desire
    to grant the client (intervention) access to their data on 
    the server (Central Services).

    For ease of use, this decision has been hardwired to "allow access"
    on Central Services. Making a GET request to this endpoint is still
    the required initial step in the OAuth 2.0 Authorization Code
    Grant (http://tools.ietf.org/html/rfc6749#section-4.1), likely
    handled by the OAuth 2.0 library used by the client.
    ---
    tags:
      - OAuth
    operationId: oauth_authorize
    parameters:
      - name: response_type
        in: formData
        description:
          Type of OAuth authorization requested.  Use "code"
        required: true
        type: string
      - name: client_id
        in: formData
        description:
          Client's unique identifier, obtained during registration
        required: true
        type: string
      - name: redirect_uri
        in: formData
        description:
          Intervention's target URI for call back. Central Services
          will include an authorization code in the call (to be
          subsequently exchanged for an access token).
        required: true
        type: string
      - name: scope
        in: formData
        description:
          Extent of authorization requested.  At this time, only 'email'
          is supported.
        required: true
        type: string
    produces:
      - application/json
    responses:
      302:
        description:
          redirect to requested redirect_uri with a valid
          authorization code. NB - this is not the bearer
          token needed for API access, but the code to be
          exchanged for such an access token. In the
          event of an error, redirection will target /oauth/errors
          of Central Services.

    """
    user = current_user()
    if not user:
        return redirect('/')
    # See "hardwired" note in docstring above
    return True
