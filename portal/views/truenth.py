"""TrueNTH API view functions"""
from flask import Blueprint, jsonify, make_response
from flask import current_app, render_template, request, url_for

from ..audit import auditable_event
from ..extensions import oauth
from .crossdomain import crossdomain
from ..models.user import current_user

truenth_api = Blueprint('truenth_api', __name__, url_prefix='/api')


@truenth_api.route('/auditlog', methods=('POST',))
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
          id: response
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      401:
        description: if missing valid OAuth token

    """
    message = request.form.get('message')
    if not message:
        return jsonify(message="missing required 'message' in post")
    auditable_event('remote message: {0}'.format(message),
                    user_id=current_user().id)
    return jsonify(message='ok')


@truenth_api.route('/portal-wrapper-html/', methods=('OPTIONS',))
@crossdomain(origin='*')
def preflight_unprotected():  # pragma: no cover
    """CORS requires preflight headers

    For in browser CORS requests, first respond to an OPTIONS request
    including the necessary Access-Control headers.

    Requires separate route for OPTIONS to avoid authorization tangles.

    """
    pass  # all work for OPTIONS done in crossdomain decorator


@truenth_api.route('/portal-wrapper-html/', defaults={'username': None})
@truenth_api.route('/portal-wrapper-html/<username>')
def portal_wrapper_html(username):
    """Returns portal wrapper for insertion at top of interventions

    Get html for the portal site UI wrapper (top-level nav elements, etc)
    This is the unauthorized version, useful prior to logging in with
    TrueNTH.  See `protected_portal_wrapper_html` for authorized
    version.
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
          Location to direct login requests.  Typically an entry
          point on the intervention, to initiate OAuth dance with
          TrueNTH.  Inclusion of this parameter affects
          the apperance of a "login" option in the portal menu.
        required: false
        type: string
      - name: username
        in: path
        description:
          Optional username, used to personalize the header.
        required: true
        type: string
    responses:
      200:
        description:
          html for direct insertion near the top of the intervention's
          page.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient


    """
    movember_profile = ''.join((
        '//',
        current_app.config['SERVER_NAME'],
        url_for('static', filename='img/movember_profile_thumb.png'),
    ))

    # workarounds till we can call protected_portal_wrapper from portal
    user = current_user()
    if user:
        if user.image_url:
            movember_profile = user.image_url
        username = username if username else user.display_name
    else:
        user = None

    html = render_template(
        'portal_wrapper.html',
        PORTAL=''.join(('//', current_app.config['SERVER_NAME'])),
        username=username,
        user=user,
        movember_profile=movember_profile,
        login_url=request.args.get('login_url')
    )
    resp = make_response(html)
    resp.headers.add('Access-Control-Allow-Origin', '*')
    resp.headers.add('Access-Control-Allow-Headers', 'X-Requested-With')
    return resp


@truenth_api.route('/protected-portal-wrapper-html', methods=('OPTIONS',))
@crossdomain()
def preflight():  # pragma: no cover
    """CORS requires preflight headers

    For in browser CORS requests, first respond to an OPTIONS request
    including the necessary Access-Control headers.

    Requires separate route for OPTIONS to avoid authorization tangles.

    """
    pass  # all work for OPTIONS done in crossdomain decorator


@truenth_api.route('/protected-portal-wrapper-html', methods=('GET',))
@oauth.require_oauth()
@crossdomain()
def protected_portal_wrapper_html():
    """Returns portal wrapper for insertion at top of interventions

    Get html for the portal site UI wrapper (top-level nav elements, etc)
    This is the authorized version, only useful after to logging in with
    TrueNTH.  See `portal_wrapper_html` for the unauthorized
    version.
    ---
    tags:
      - TrueNTH
    operationId: getProtectedPortalWrapperHTML
    produces:
      - text/html
    responses:
      200:
        description:
          html for direct insertion near the top of the intervention's
          page.
      401:
        description: if missing valid OAuth token

    """
    movember_profile = ''.join((
        '//',
        current_app.config['SERVER_NAME'],
        url_for('static', filename='img/movember_profile_thumb.png'),
    ))

    user = current_user()
    if user.image_url:
        movember_profile = user.image_url

    html = render_template(
        'portal_wrapper.html',
        PORTAL=''.join(('//', current_app.config['SERVER_NAME'])),
        username=user.display_name,
        user=user,
        movember_profile=movember_profile,
    )
    return make_response(html)
