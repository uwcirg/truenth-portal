"""Extensions used at application level"""

# SQLAlchemy provides the database object relational mapping (ORM)
from flask.ext.sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Flask-User
from flask.ext.user import UserManager, SQLAlchemyAdapter
from .models.user import User
db_adapter = SQLAlchemyAdapter(db, User)
user_manager = UserManager(db_adapter)

# Flask-OAuthLib provides OAuth between the Portal and the Interventions
from functools import wraps
from flask import abort, request
from flask_oauthlib.provider import OAuth2Provider
from .models.user import current_user

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
           return the effecively undecorated function.

        """
        def wrapper(eff):
            """preserve name and docstrings on 'eff'

            see: http://stackoverflow.com/questions/308999/what-does-functools-wraps-do

            """
            @wraps(eff)
            def decorated(*args, **kwargs):
                """decorate the 'eff' function"""
                # TESTING backdoor
                if self.app.config.get('TESTING'):
                    return eff(*args, **kwargs)
                # Local login backdoor
                if current_user():
                    return eff(*args, **kwargs)

                # Unmodified superclass method follows
                for func in self._before_request_funcs:
                    func()

                if hasattr(request, 'oauth') and request.oauth:
                    return eff(*args, **kwargs)

                valid, req = self.verify_request(scopes)

                for func in self._after_request_funcs:
                    valid, req = func(valid, req)

                if not valid:
                    if self._invalid_response:
                        return self._invalid_response(req)
                    return abort(401)
                request.oauth = req
                return eff(*args, **kwargs)
            return decorated
        return wrapper

oauth = OAuthOrAlternateAuth()


# Flask-Authomatic provides OAuth between the Portal and upstream
# identity providers such as Facebook
from authomatic.extras.flask import FlaskAuthomatic
from authomatic.providers import oauth2
from .config import early_app_config_access

app_config = early_app_config_access()
fa = FlaskAuthomatic(
    config={
        'fb': {
            'class_': oauth2.Facebook,
            'consumer_key': app_config['CONSUMER_KEY'],
            'consumer_secret': app_config['CONSUMER_SECRET'],
            'scope': ['public_profile', 'email'],
        },
    },
    secret=app_config['SECRET_KEY'],
    debug=True,
)
