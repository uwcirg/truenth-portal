"""TrueNTH API view functions"""
from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.exceptions import Unauthorized

from ..audit import auditable_event
from ..csrf import csrf
from ..extensions import oauth
from ..models.client import validate_origin
from ..models.user import current_user
from ..usage_monitor import mark_usage
from .crossdomain import crossdomain

truenth_api = Blueprint('truenth_api', __name__, url_prefix='/api')


@truenth_api.route("/ping", methods=('POST', 'OPTIONS'))
@csrf.portal_exempt
@crossdomain()
def ping():
    """POST request prolong session by reseting cookie timeout"""
    current_app.logger.debug("ping received")
    session.modified = True
    mark_usage()
    return 'OK'


@truenth_api.route('/auditlog', methods=('POST',))
@crossdomain()
@oauth.require_oauth()
def auditlog_addevent():
    """Add event to audit log

    API for client applications to add any event to the audit log.  The message
    will land in the same audit log as any auditable internal event, including
    recording the authenticated user making the call.

    Returns a json friendly message, i.e. {"message": "ok"}
    ---
    operationId: auditlog_addevent
    tags:
      - TrueNTH
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          id: message
          required:
            - message
          properties:
            message:
              type: string
              description: message text
    responses:
      200:
        description: successful operation
        schema:
          id: response_ok
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      401:
        description: if missing valid OAuth token
    security:
      - ServiceToken: []

    """
    message = request.form.get('message')
    context = request.form.get('context', 'other')
    if not message:
        return jsonify(message="missing required 'message' in post")
    auditable_event('remote message: {0}'.format(message), context=context,
                    user_id=current_user().id, subject_id=current_user().id)
    return jsonify(message='ok')


@truenth_api.route('/portal-wrapper-html/', methods=('GET', 'OPTIONS'))
@crossdomain()
def portal_wrapper_html():
    """Returns portal wrapper for insertion at top of interventions

    Get html for the portal site UI wrapper (top-level nav elements, timeout code, piwik analytics, etc)

    CORS headers will only be included when the request includes well defined
    Origin header.

    To assist in logic decisions on client pages, the javascript variable
    `truenth_authenticated` of type boolean included in the response will
    accurately describe the user's athenticated status.

    ---
    tags:
      - TrueNTH
    operationId: getPortalWrapperHTML
    produces:
      - text/html
    parameters:
      - name: login_url
        in: query
        description:
          URL on intervention to direct login requests.  Typically an entry
          point on the intervention, to initiate OAuth dance with
          TrueNTH.  Inclusion of this parameter affects
          the apperance of a "login" option in the portal menu, but only
          displayed if the user has not logged in.
        required: false
        type: string
      - name: disable_links
        in: query
        description:
          If present, with any value, all links will be removed.  Useful
          during sessions where any navigation outside of the main well
          is discouraged.
        required: false
        type: string
    responses:
      200:
        description:
          html for direct insertion near the top of the intervention's
          page.
      403:
        description:
          if a login_url is provided with an origin other than one
          registered as a client app or intervention
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """
    # Unlike all other oauth protected resources, we manually check
    # if it's a valid oauth request as this resource is also available prior
    # to logging in.
    valid, req = oauth.verify_request(['email'])
    if valid:
        user = req.user
    else:
        user = current_user()

    login_url = request.args.get('login_url')
    if login_url and not user:
        try:
            validate_origin(login_url)
        except Unauthorized:
            current_app.logger.warning(
                "invalid origin on login_url `%s` from referer `%s`",
                login_url, request.headers.get('Referer'))
            return make_response("login_url lacks a valid origin: {}".format(
                login_url)), 403
    else:
        login_url = None

    if user and user.image_url:
        movember_profile = user.image_url
    else:
        movember_profile = ''.join((
            '//',
            current_app.config['SERVER_NAME'],
            url_for('static', filename='img/movember_profile_thumb.png'),
        ))

    def branded_logos():
        """return path to branded logos if called for in tuple (lg, small)"""
        if 'brand' in request.args:
            brand_name = request.args.get('brand')
            return (
                url_for('static',
                        filename="img/{}.png".format(brand_name),
                        _external=True),
                url_for('static',
                        filename="img/{}_sm.png".format(brand_name),
                        _external=True)
            )

    def expires_in():
        """compute remaining seconds on session"""
        expires = current_app.permanent_session_lifetime.total_seconds()
        return expires

    cookie_timeout = request.cookies.get('SS_INACTIVITY_TIMEOUT')
    disable_links = True if 'disable_links' in request.args else False
    html = render_template(
        'portal_wrapper.html',
        PORTAL=''.join(('//', current_app.config['SERVER_NAME'])),
        user=user,
        movember_profile=movember_profile,
        login_url=login_url,
        branded_logos=branded_logos(),
        enable_links=not disable_links,
        expires_in=cookie_timeout if cookie_timeout else expires_in()
    )
    return make_response(html)


@truenth_api.route('/portal-footer-html/', methods=('GET', 'OPTIONS'))
@crossdomain()
def portal_footer_html():
    """Returns portal footer for insertion at bottom of interventions

    Get html for the portal site UI footer

    CORS headers will only be included when the request includes well defined
    Origin header.

    ---
    tags:
      - TrueNTH
    operationId: getPortalFooterHTML
    produces:
      - text/html
    responses:
      200:
        description:
          html for direct insertion near the bottom of the intervention's
          page.
    security:
      - ServiceToken: []

    """
    # Unlike all other oauth protected resources, we manually check
    # if it's a valid oauth request as this resource is also available prior
    # to logging in.
    valid, req = oauth.verify_request(['email'])
    if valid:
        user = req.user
    else:
        user = current_user()

    html = render_template(
        'portal_footer.html',
        PORTAL=''.join(('//', current_app.config['SERVER_NAME'])),
        user=user
    )
    return make_response(html)


# Deprecated rewrites follow
@truenth_api.route('/portal-wrapper-html/<username>',
                   methods=('GET', 'OPTIONS'))
@crossdomain()
def depricated_portal_wrapper_html(username):
    current_app.logger.warning("use of depricated API %s from referer %s",
                               request.url, request.headers.get('Referer'))
    return portal_wrapper_html()


@truenth_api.route('/protected-portal-wrapper-html', methods=('GET', 'OPTIONS'))
@crossdomain()
def protected_portal_wrapper_html():
    current_app.logger.warning("use of depricated API %s from referer %s",
                               request.url, request.headers.get('Referer'))
    return portal_wrapper_html()
