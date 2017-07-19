from flask import abort, current_app, Blueprint, request
from flask_wtf.csrf import CSRFProtect

from .models.user import current_user

csrf = CSRFProtect()


csrf_blueprint = Blueprint('csrf_blueprint', __name__)


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

    # Look for legit OAuth requests, and exclude these from csrf protection
    if request.headers and request.headers.get('Authorization'):
        # 'Authorization' will have bearer on oauth, but we don't yet know
        # if it's valid.  That will be handled in time with the OAuth
        # decorators on the respecive views.  Confirm we don't ALSO have what
        # looks like a valid local cookie auth, as they shouldn't ever both
        # be present.

        if request.headers['Authorization'].startswith('Bearer '):
            # As this function is called before the OAuth decorator has had
            # a chance, we should never see a current user (unless one is tied
            # to a local login session).
            if current_user():
                current_app.logger.error(
                    "Local access and OAuth appear mixed {} {}".format(
                        request.method, request.path))
                abort(401, "Local access and OAuth can not be mixed")
            return

    csrf.protect()
    return
