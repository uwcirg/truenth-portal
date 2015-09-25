"""Auth related view functions"""
import base64
import hashlib
import hmac
import json
import requests
from urlparse import urlparse, parse_qs
from flask import Blueprint, jsonify, redirect, current_app
from flask import render_template, request, session, abort, url_for
from flask.ext.login import login_user, logout_user
from flask.ext.user import roles_required
from werkzeug.security import gen_salt

from ..models.auth import AuthProvider, Client, Token
from ..models.user import current_user, User, Role, UserRoles
from ..extensions import db, fa, oauth

auth = Blueprint('auth', __name__)


@auth.route('/deauthorized', methods=('POST',))
def deauthorized():
    """Callback URL configured on facebook when user deauthorizes

    We receive POST data when a user deauthorizes the session
    between Central Services and Facebook.  The POST includes
    a signed_request, decoded as seen below.

    Configuration set on Facebook Developer pages:
      app->settings->advanced->Deauthorize Callback URL

    """
    def base64_url_decode(s):
        """url safe base64 decoding method"""
        padding_factor = (4 - len(s) % 4)
        s += "="*padding_factor
        return base64.b64decode(unicode(s).translate(
            dict(zip(map(ord, u'-_'), u'+/'))))

    encoded_sig, payload = request.form['signed_request'].split('.')
    sig = base64_url_decode(encoded_sig)
    data = base64_url_decode(payload)

    secret = current_app.config['CONSUMER_SECRET']
    expected_sig = hmac.new(secret, msg=payload,
            digestmod=hashlib.sha256).digest()
    if expected_sig != sig:
        current_app.logger.error("Signed request from FB doesn't match!")
        return jsonify(error='bad signature')

    current_app.logger.debug("data: %s", str(data))
    data = json.loads(data)
    # Should probably remove all tokens obtained during this session
    # for now, just logging the event.
    message = 'User {0} deauthorized Central Services from Facebook'.\
            format(data['user_id'])
    current_app.logger.info(message)
    return jsonify(message=message)


@auth.route('/login')
@fa.login('fb')
def login():
    """login view function

    After successful authorization at OAuth server, control
    returns here.  The user's ID and the remote oauth bearer
    token are retained in the session for subsequent use.

    """
    # Unittesting backdoor - see tests.login() for use
    if current_app.config['TESTING']:
        id = request.args.get('user_id')
        assert (int(id) < 10)  # allowed for test users only!
        session['id'] = id
        user = current_user()
        login_user(user)
        return redirect('/')

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
            # If client auth was pushed aside, resume now
            if 'pending_authorize_args' in session:
                args = session['pending_authorize_args']
                current_app.logger.debug("redirecting to interrupted " +
                    "client authorization: %s", str(args))
                del session['pending_authorize_args']
                return redirect(url_for('.authorize', **args))
            else:
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
    user_id = session['id']
    current_app.logger.debug("Logout user.id %d", user_id)

    delete_facebook_authorization = False  # Fencing out for now
    ap = AuthProvider.query.filter_by(provider='facebook',
            user_id=user_id).first()
    if ap and delete_facebook_authorization:
        headers = {'Authorization':
            'Bearer {0}'.format(session['remote_token'])}
        url = "https://graph.facebook.com/{0}/permissions".\
            format(ap.provider_id)
        requests.delete(url, headers=headers)

    logout_user()
    session.clear()

    # Inform any client apps of this event.  Look for tokens this
    # user obtained, and notify those clients of the event
    tokens = Token.query.filter_by(user_id=user_id).all()
    for token in tokens:
        client = Client.query.filter_by(client_id=token.client_id).first()
        client.notify({'event':'logout', 'user_id':user_id})

        # Invalidate the access token by deletion
        db.session.delete(token)
    db.session.commit()
    return redirect('/')


@auth.route('/client', methods=('GET', 'POST'))
@roles_required('application_developer')
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
      - text/html
    responses:
      200:
        description: successful operation
        schema:
          id: client_response
          required:
            - App ID
            - App Secret
            - Site URL
          properties:
            App ID:
              type: string
              description:
                Identification unique to a Central Serivce application.
                Pass as `client_id` in OAuth Authorization Code Grant
                calls to obtain an authorization token
            App Secret:
              type: string
              description:
                Safe guarded secret used by Intervention's OAuth
                client library.  Pass as `client_secret` in calls
                to `/oauth/token`
            Site URL:
              type: string
              description:
                Application's site Origin or URL.
                Required to include the origin of OAuth callbacks
                and site origins making in-browser requests via CORS

    """
    user = current_user()
    if request.method == 'GET':
        return render_template('client_add.html')
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
    return redirect(url_for('.client_edit', client_id=item.client_id))


@auth.route('/client/<client_id>', methods=('GET', 'POST'))
@roles_required('application_developer')
def client_edit(client_id):
    """client edit

    View details and edit settings for a Central Services client (also
    known as an Intervention or App).
    ---
    tags:
      - OAuth
    operationId: client_edit
    parameters:
      - name: client_id
        in: path
        required: true
        description: The App ID (client_id) from client registration
        type: string
      - name: callback_url
        in: formData
        description:
          An optional callback URL to be hit on significant
          events, such as a user terminating a session via logout
        required: false
        type: string
    produces:
      - text/html
    responses:
      200:
        description: successful operation
        schema:
          id: client_edit_response
          required:
            - App ID
            - App Secret
            - Site URL
            - Callback URL
          properties:
            App ID:
              type: string
              description:
                Identification unique to a Central Serivce application.
                Pass as `client_id` in OAuth Authorization Code Grant
                calls to obtain an authorization token
            App Secret:
              type: string
              description:
                Safe guarded secret used by Intervention's OAuth
                client library.  Pass as `client_secret` in calls
                to `/oauth/token`
            Site URL:
              type: string
              description:
                Application's site Origin or URL.
                Required to include the origin of OAuth callbacks
                and site origins making in-browser requests via CORS
            Callback URL:
              type: string
              description:
                Callback URL hit on significant events such as a
                session termination.  If defined, a POST to the
                callback will include a "signed_request" using
                the client_secret.  See numerous resources
                published for decoding Facebook signed_request, as
                the format is identical.

    """
    client = Client.query.get(client_id)
    if not client:
        abort(404)
    user = current_user()
    current_user().check_role(permission='edit', other_id=client.user_id)
    if request.method == 'GET':
        return render_template('client_edit.html', client=client)

    if request.form.get('delete'):
        db.session.delete(client)
    else:
        callback_url = request.form.get('callback_url', None)
        if callback_url and callback_url != 'None':
            client.callback_url = callback_url
        redirect_uri = request.form.get('redirect_uri', None)
        if redirect_uri and redirect_uri != 'None':
            client._redirect_uris = redirect_uri
        db.session.add(client)
    db.session.commit()
    return redirect(url_for('.clients_list'))


@auth.route('/clients')
@roles_required('application_developer')
def clients_list():
    """clients list

    List all clients created by the authenticated user.
    ---
    tags:
      - OAuth
    operationId: clients_list
    produces:
      - text/html
    responses:
      200:
        description: successful operation
        schema:
          id: clients_list_response
          required:
            - App ID
            - Site URL
          properties:
            App ID:
              type: string
              description:
                Identification unique to a Central Serivce application.
                Pass as `client_id` in OAuth Authorization Code Grant
                calls to obtain an authorization token
            Site URL:
              type: string
              description:
                Application's site Origin or URL.
                Required to include the origin of OAuth callbacks
                and site origins making in-browser requests via CORS

    """
    user = current_user()
    clients = Client.query.filter_by(user_id=user.id).all()
    return render_template('clients_list.html', clients=clients)


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


@auth.route('/oauth/authorize', methods=('GET', 'POST'))
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
        in: query
        description:
          Type of OAuth authorization requested.  Use "code"
        required: true
        type: string
      - name: client_id
        in: query
        description:
          Client's unique identifier, obtained during registration
        required: true
        type: string
      - name: redirect_uri
        in: query
        description:
          Intervention's target URI for call back. Central Services
          will include an authorization code in the call (to be
          subsequently exchanged for an access token).  May optionally
          include an encoded 'next' value in its query string, or pass
          'next' as a separate parameter.
        required: true
        type: string
      - name: scope
        in: query
        description:
          Extent of authorization requested.  At this time, only 'email'
          is supported.
        required: true
        type: string
      - name: next
        in: query
        description:
          Target for redirection after authorization is complete
        required: false
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
    # Likely entry point for OAuth dance.  Capture the 'next' target
    # in the session for redirection after dance concludes
    if 'next' in request.args:
        current_app.logger.debug('storing session[next]: %s',
            request.args.get('next'))
        session['next'] = request.args['next']
    else:
        # Pluck the next out of the redirect_uri, if there
        parsed = urlparse(request.args['redirect_uri'])
        qs = parse_qs(parsed.query)
        if 'next' in qs:
            current_app.logger.debug('storing session[next]: %s',
                qs['next'])
            session['next'] = qs['next'][0]

    user = current_user()
    if not user:
        # Entry point when intervetion is requesting OAuth token, but
        # the user has yet to authenticate via FB or otherwise.  Need
        # to retain the request, and replay after Central Services login
        # has completed.
        current_app.logger.debug('Postponing oauth client authorization' +
            ' till user authenticates with CS: ', str(request.args))
        session['pending_authorize_args'] = request.args 

        return redirect('/')
    # See "hardwired" note in docstring above
    return True
