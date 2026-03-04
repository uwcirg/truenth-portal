"""Extensions used at application level

Generally the objects instantiated here are needed for imports
throughout the system, but require factory pattern initialization
once the flask `app` comes to life.

Defined here to break the circular dependencies.  See `app.py` for
additional configuration of most objects defined herein.

"""
# Flask-OAuthLib provides OAuth between the Portal and the Interventions
from functools import wraps

# Babel is used for i18n
# Flask-Mail is used for email communication
# ReCaptcha is used for form verification
# Flask-Session provides server side sessions
# Flask-User
from flask import abort, request
from flask_babel import Babel
from flask_mail import Mail
from flask_oauthlib.provider import OAuth2Provider
from flask_recaptcha import ReCaptcha
from flask_user import SQLAlchemyAdapter, UserManager
from flask_user import signals as flask_user_signals
from sqlalchemy import func

from .csrf import csrf
from .database import db
from .models.login import login_user
from .models.user import User, current_user
from .session import RedisSameSiteSession as Session

class PortalUserManager(UserManager):
    """UserManager with safer case-insensitive user lookups."""

    def find_user_by_email(self, email):
        """Case-insensitive user lookup by email without wildcard semantics."""
        if not email:
            return None, None

        UserModel = getattr(self.db_adapter, "UserClass", User)
        user = UserModel.query.filter(
            func.lower(UserModel.email) == func.lower(email)
        ).first()
        return user, None

    def find_user_by_username(self, username):
        """Case-insensitive user lookup by username without wildcard semantics."""
        if not username:
            return None

        UserModel = getattr(self.db_adapter, "UserClass", User)
        user = UserModel.query.filter(
            func.lower(UserModel.username) == func.lower(username)
        ).first()
        return user


# Ensure Flask-User exposes a 'user_password_failed' signal even if the
# installed version does not define it yet.
if not hasattr(flask_user_signals, "user_password_failed"):
    flask_user_signals.user_password_failed = (
        flask_user_signals._signals.signal("user.password_failed")
    )


db_adapter = SQLAlchemyAdapter(db, User)
user_manager = PortalUserManager(db_adapter)


class OAuthOrAlternateAuth(OAuth2Provider):
    """Specialize OAuth2Provider with alternate authorization"""

    def __init__(self, app=None):
        super(OAuthOrAlternateAuth, self).__init__(app)

    def require_oauth(self, *scopes):
        """Specialze the superclass decorator with alternates

        This method is intended to be in lock step with the
        super class, with the following two exceptions:

        1. if actively "TESTING", skip oauth and return
           the function, effectively undecorated.

        2. if the user appears to be locally logged in (i.e. browser
           session cookie with a valid user.id),
           return the effectively undecorated function.

        """

        def wrapper(eff):
            """preserve name and docstrings on 'eff'

            see: http://stackoverflow.com/questions/308999/what-does-functools-wraps-do

            """

            @csrf.exempt
            @wraps(eff)
            def decorated(*args, **kwargs):  # pragma: no cover
                """decorate the 'eff' function"""
                # TESTING backdoor
                if self.app.config.get('TESTING'):
                    return eff(*args, **kwargs)
                # Local login backdoor
                if current_user():
                    return eff(*args, **kwargs)

                # Superclass method follows
                # all MODs clearly marked
                for func in self._before_request_funcs:
                    func()

                if hasattr(request, 'oauth') and request.oauth:
                    # Start MOD
                    # Need to log oauth user in for flask-user roles, etc.
                    login_user(request.oauth.user)
                    # End MOD
                    return eff(*args, **kwargs)

                valid, req = self.verify_request(scopes)

                for func in self._after_request_funcs:
                    valid, req = func(valid, req)

                if not valid:
                    if self._invalid_response:
                        return self._invalid_response(req)
                    return abort(401)
                request.oauth = req
                # Start MOD
                # Need to log oauth user in for flask-user roles, etc.
                login_user(request.oauth.user)
                # End MOD
                return eff(*args, **kwargs)

            return decorated

        return wrapper

oauth = OAuthOrAlternateAuth()

mail = Mail()

session = Session()

babel = Babel()

recaptcha = ReCaptcha()
