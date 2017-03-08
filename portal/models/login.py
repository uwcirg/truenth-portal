"""Module for common login hook"""

from flask_login import login_user as flask_user_login
from flask_login import current_user as flask_login_current_user
from flask_user import _call_or_get

from .encounter import initiate_encounter


def login_user(user, auth_method):
    """Common entry point for all login flows - direct here for bookkeeping

    Logs user into flask_user system and generates the encounter used to track
    authentication method.

    """
    if not _call_or_get(flask_login_current_user.is_authenticated):
        flask_user_login(user)
    initiate_encounter(user, auth_method)
