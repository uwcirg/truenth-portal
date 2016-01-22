"""Auth related view functions"""
import base64
from datetime import datetime
import hashlib
import hmac
import json
import requests
from urlparse import urlparse, parse_qs
from authomatic.adapters import WerkzeugAdapter
from flask import Blueprint, jsonify, redirect, current_app, make_response
from flask import render_template, request, session, abort, url_for
from flask.ext.login import login_user, logout_user
from flask.ext.user import roles_required
from flask.ext.user.signals import user_logged_in, user_registered
from flask_wtf import Form
from wtforms import TextField, validators
from werkzeug.security import gen_salt
from validators import url as url_validation

from ..audit import auditable_event
from ..models.auth import AuthProvider, Client, Token, create_service_token
from ..models.relationship import RELATIONSHIP
from ..models.role import ROLE
from ..models.user import add_authomatic_user, add_default_role
from ..models.user import current_user, get_user, User
from ..extensions import authomatic, db, oauth
from ..template_helpers import split_string

auth = Blueprint('auth', __name__)


@auth.context_processor
def utility_processor():
    return dict(split_string=split_string)


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


def flask_user_login_event(app, user, **extra):
    auditable_event("local user login", user_id=user.id)

def flask_user_registered_event(app, user, **extra):
    auditable_event("local user registered", user_id=user.id)
    add_default_role(user)


# Register functions to receive signals from flask_user
user_logged_in.connect(flask_user_login_event)
user_registered.connect(flask_user_registered_event)


@auth.route('/next-after-login')
def next_after_login():
    """Redirect to appropriate target depending on client auth status

    When client applications request OAuth tokens, we sometimes need
    to postpone the action of authorizing the client while the user
    logs in to Central Services.

    After completing authentication with Central Services, this handles
    redirecting the browser to the appropriate target (either resume
    the client auth in process or the root).

    Implemented as a view method for integration with flask-user config.

    """
    # If client auth was pushed aside, resume now
    if 'pending_authorize_args' in session:
        args = session['pending_authorize_args']
        current_app.logger.debug("redirecting to interrupted " +
            "client authorization: %s", str(args))
        del session['pending_authorize_args']
        return redirect(url_for('auth.authorize', **args))
    else:
        return redirect('/')


@auth.route('/login/<provider_name>/')
def login(provider_name):
    """login view function

    After successful authorization at OAuth server, control
    returns here.  The user's ID and the remote oauth bearer
    token are retained in the session for subsequent use.

    """
    def testing_backdoor(user_id):
        "Unittesting backdoor - see tests.login() for use"
        assert int(user_id) < 10  # allowed for test users only!
        session['id'] = user_id
        user = current_user()
        login_user(user)
        return redirect('/')

    def picture_url(result):
        """Using OAuth result, fetch the user's picture URL"""
        image_url = result.user.picture
        if provider_name == 'facebook':
            # Additional request needed for FB profile image
            url = '?'.join(("https://graph.facebook.com/{0}/picture",
                "redirect=false")).format(result.user.id)
            response = result.provider.access(url)
            if response.status == 200:
                image_url = response.data['data']['url']
        return image_url

    if provider_name == 'TESTING' and current_app.config['TESTING']:
        return testing_backdoor(request.args.get('user_id'))

    response = make_response()
    adapter = WerkzeugAdapter(request, response)
    result = authomatic.login(adapter, provider_name)

    if current_user():
        return redirect('/')
    if result:
        if result.error:
            current_app.logger.error(result.error.message)
            return result.error.message
        elif result.user:
            current_app.logger.debug("Successful authentication at %s",
                    provider_name)
            if not (result.user.name and result.user.id):
                result.user.update()
                image_url = picture_url(result)

            # Success - add or pull this user to/from database
            ap = AuthProvider.query.filter_by(provider=provider_name,
                    provider_id=result.user.id).first()
            if ap:
                auditable_event("login via {0}".format(provider_name),
                                user_id=ap.user_id)
                user = User.query.filter_by(id=ap.user_id).first()
                user.image_url=image_url
                db.session.commit()
            else:
                # Confirm we haven't seen user from a different IdP
                user = User.query.filter_by(email=result.user.email).\
                        first() if result.user.email else None

                if not user:
                    user = add_authomatic_user(result.user, image_url)
                    db.session.commit()
                    auditable_event("register new user via {0}".\
                                    format(provider_name), user_id=user.id)
                else:
                    auditable_event("login user via NEW IdP {0}".\
                                    format(provider_name), user_id=user.id)
                    user.image_url=image_url

                ap = AuthProvider(provider=provider_name,
                        provider_id=result.user.id,
                        user_id=user.id)
                db.session.add(ap)
                db.session.commit()
            session['id'] = user.id
            session['remote_token'] = result.provider.credentials.token
            login_user(user)
            return next_after_login()
    else:
        return response


@auth.route('/logout')
def logout():
    """logout view function

    Logs user out by requesting the previously granted permission to
    use authenticated resources be deleted from the OAuth server, and
    clearing the browser session.

    """
    user = current_user()
    user_id = user.id if user else None

    def delete_facebook_authorization(user_id):
        """Remove OAuth authorization for Central Services on logout

        If the user has ever authorized Central Services via Facebook,
        tell facebook to delete the authorization now (on logout).

        NB - this isn't standard OAuth behavior, users only expect to
        authorize Central Services one time to use their Facebook
        authentication.

        """
        ap = AuthProvider.query.filter_by(provider='facebook',
                user_id=user_id).first()
        if ap:
            headers = {'Authorization':
                'Bearer {0}'.format(session['remote_token'])}
            url = "https://graph.facebook.com/{0}/permissions".\
                format(ap.provider_id)
            requests.delete(url, headers=headers)


    def notify_clients(user_id):
        """Inform any client apps of the logout event.

        Look for tokens this user obtained, and notify those clients
        of the logout event

        """
        if not user_id:
            return
        for token in Token.query.filter_by(user_id=user_id):
            c = Client.query.filter_by(client_id=token.client_id).first()
            c.notify({'event': 'logout', 'user_id': user_id,
                    'refresh_token': token.refresh_token})
            # Invalidate the access token by deletion
            db.session.delete(token)
        db.session.commit()


    if user_id:
        auditable_event("logout", user_id=user_id)
        # delete_facebook_authorization()  #Not using at this time

    logout_user()
    session.clear()
    notify_clients(user_id)
    return redirect('/')


class ClientEditForm(Form):
    """wtform class for validation during client edits"""
    application_origins = TextField('Application URL',
            validators=[validators.Required()])
    callback_url = TextField('Callback URL',
            validators=[validators.optional(),
                validators.URL(require_tld=False)])

    def validate_application_origins(form, field):
        """Custom validation to handle multiple, space delimited URLs"""
        origins = field.data.split()
        for url in origins:
            if not url_validation(url, require_tld=False):
                raise validators.ValidationError("Invalid URL")


@auth.route('/client', methods=('GET', 'POST'))
@roles_required(ROLE.APPLICATION_DEVELOPER)
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
      - name: application_origins
        in: formData
        description:
          Application origins. The service will only redirect to URIs in
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
                Application's site Origin(s) or URL(s).
                Required to include the origin of OAuth callbacks
                and site origins making in-browser requests via CORS

    """
    user = current_user()
    form = ClientEditForm()
    if not form.validate_on_submit():
        return render_template('client_add.html', form=form)
    client = Client(
        client_id=gen_salt(40),
        client_secret=gen_salt(50),
        _redirect_uris=form.application_origins.data,
        _default_scopes='email',
        user_id=user.id,
    )
    db.session.add(client)
    db.session.commit()
    auditable_event("added intervention/client {}".format(
        client.client_id), user_id=user.id)
    return redirect(url_for('.client_edit', client_id=client.client_id))


@auth.route('/client/<client_id>', methods=('GET', 'POST'))
@roles_required(ROLE.APPLICATION_DEVELOPER)
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
    user.check_role(permission='edit', other_id=client.user_id)

    form = ClientEditForm(obj=client)

    def lookup_service_token(client):
        client_user = get_user(client.user_id)
        sponsor_relationship = [r for r in client_user.relationships if
                                r.relationship.name == RELATIONSHIP.SPONSOR]
        if (sponsor_relationship):
            assert len(sponsor_relationship) == 1
            return Token.query.filter_by(client_id=client.client_id,
                user_id=sponsor_relationship[0].other_user_id).first()
        return None

    if not form.validate_on_submit():
        return render_template('client_edit.html', client=client, form=form,
                              service_token=lookup_service_token(client))

    redirect_target = url_for('.clients_list')
    if request.form.get('delete'):
        auditable_event("deleted intervention/client {}".format(
            client.client_id), user_id=user.id)
        db.session.delete(client)
    elif request.form.get('service_token'):
        # limiting this to the client owner as sponsorship gets messy
        if user.id != client.user_id:
            raise ValueError("only client owner can add service accounts")
        existing = lookup_service_token(client)
        if existing:
            db.session.delete(existing)
        service_user = user.add_service_account()
        token = create_service_token(client=client, user=service_user)
        redirect_target = url_for('.client_edit', client_id=client.client_id)
    else:
        auditable_event("edited intervention/client {}"
                        "by".format(client.client_id), user_id=user.id)
        auditable_event("before: {}".format(client), user_id=user.id)
        form.populate_obj(client)
        auditable_event("after: {}".format(client), user_id=user.id)
    db.session.commit()
    return redirect(redirect_target)


@auth.route('/clients')
@roles_required(ROLE.APPLICATION_DEVELOPER)
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


@auth.route('/oauth/token-status')
@oauth.require_oauth()
def token_status():
    """Return remaining valid time and other info for oauth token

    Endpoint for clients needing to double check status on a token.
    Returns essentially the same JSON obtained from the /oauth/token
    call, with `expires_in` updated to show remaining seconds.

    ---
    tags:
      - OAuth
    operationId: token_status
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: token_status
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
            token_type:
              type: string
              description: Type of access token, always 'Bearer'
            expires_in:
              type: integer
              format: int64
              description:
                Number of seconds for which the access token will
                remain valid
            refresh_token:
              type: string
              description:
                Use to refresh an access token, in place of the
                authorizion token.
            scopes:
              type: string
              description: The authorized scopes.

    """
    token_type, access_token = request.headers.get('Authorization').split()
    token = Token.query.filter_by(access_token=access_token).first()
    expires_in = token.expires - datetime.utcnow()
    return jsonify(access_token=access_token,
            refresh_token=token.refresh_token, token_type=token_type,
            expires_in=expires_in.seconds, scopes=token._scopes)


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
            token_type:
              type: string
              description: Type of access token, always 'Bearer'
            expires_in:
              type: integer
              format: int64
              description:
                Number of seconds for which the access token will
                remain valid
            refresh_token:
              type: string
              description:
                Use to refresh an access token, in place of the
                authorizion token.
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
            current_app.logger.debug('storing ssession[next]: %s',
                qs['next'])
            session['next'] = qs['next'][0]

    user = current_user()
    if not user:
        # Entry point when intervetion is requesting OAuth token, but
        # the user has yet to authenticate via FB or otherwise.  Need
        # to retain the request, and replay after Central Services login
        # has completed.
        current_app.logger.debug('Postponing oauth client authorization' +
            ' till user authenticates with CS: %s', str(request.args))
        session['pending_authorize_args'] = request.args 

        return redirect('/')
    # See "hardwired" note in docstring above
    return True
