from flask import Blueprint, abort, current_app, request
from flask_wtf.csrf import CSRFProtect

from .models.user import current_user

csrf_blueprint = Blueprint('csrf_blueprint', __name__)


class CSRFProtectPortal(CSRFProtect):
    """Specialize CSRFProtect to handle OAuth exclusions"""

    def __init__(self, app=None):
        """Add our own exemption set for the extended needs"""
        self._portal_exempt_views = set()
        super(CSRFProtectPortal, self).__init__(app)

    def portal_exempt(self, view):
        """Mark a view to be excluded from *all* CSRF protection.

        To prevent any csrf protection on a view, this method will add the view
        to both the superclass' exempt list and the local one.

        To preserve checks for non OAuth use of a view, use the `@csrf.exempt`
        decorator.  This is the far more typical use.  There should be a strong
        case for defending why a view requires full portal exemption from csrf
        protection.

        ::

            @app.route('/some-view', methods=['POST'])
            @csrf.portal_exempt
            def some_view():
                ...

        """
        # Add to super class' exempt list
        super(CSRFProtectPortal, self).exempt(view)

        if isinstance(view, basestring):
            view_location = view
        else:
            view_location = '%s.%s' % (view.__module__, view.__name__)

        # Also preserve in portal_exempt list
        self._portal_exempt_views.add(view_location)
        return view


@csrf_blueprint.before_app_request
def csrf_protect():
    """ Protect views from Cross Site Resource Forgery (CSRF)

    All oauth endpoints must include the `@csrf.exempt` decorator in order
    to avoid requiring csrf tokens for legitamite OAuth client use.

    Given that many of these same endpoints are also used by the UI and other
    user agent access (READ: vulnerable to CSRF attacks), this function is
    invoked before every request (regardless of blueprint) to determine if csrf
    protection should be included.

    """
    # Only protect the configured verbs
    if request.method not in current_app.config['WTF_CSRF_METHODS']:
        return

    # Don't get in the way of the initial oauth dance.
    if request.path.startswith('/oauth/'):
        return

    # Backdoor for testing
    if current_app.config.get('TESTING') is True:
        return

    # exclude any named by portal_exclude decorator
    view = current_app.view_functions.get(request.endpoint)
    if view:
        dest = '%s.%s' % (view.__module__, view.__name__)
        if dest in csrf._portal_exempt_views:
            return

    # Look for legit OAuth requests, and exclude these from csrf protection
    if request.headers.get('Authorization'):
        # 'Authorization' will contain a Bearer token on OAuth requests.
        # Although we don't yet know if it's valid, that will be handled in
        # time with the OAuth decorators on the respecive views.

        # Confirm we don't ALSO have what looks like a valid local cookie auth,
        # as they shouldn't ever both be present.  Both might indicate a fake
        # OAuth token attempt to thwart this csrf protection.

        if request.headers['Authorization'].startswith('Bearer '):
            # As this function is called before the OAuth decorator has had
            # a chance, we should never see a current user (unless one is tied
            # to a local login session).  We will however get a valid user back
            # for a local user / cookie auth.
            if current_user():
                current_app.logger.error(
                    "Local access and OAuth appear mixed {} {}".format(
                        request.method, request.path))
                abort(401, "Local access and OAuth can not be mixed")
            return

    csrf.protect()
    return


csrf = CSRFProtectPortal()
