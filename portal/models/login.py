"""Module for common login hook"""

from flask import current_app, session
from flask_login import (
    current_user as flask_login_current_user,
    login_user as flask_user_login,
)
from flask_user import _call_or_get

from .encounter import initiate_encounter


def login_user(user, auth_method=None):
    """Common entry point for all login flows - direct here for bookkeeping

    :param user: The user to log in
    :param auth_method: If known, the method used to log in.

    Logs user into flask_user system and generates the encounter used to track
    authentication method.

    """
    if not _call_or_get(flask_login_current_user.is_authenticated):
        flask_user_login(user)

    # Reuse active encounter if available
    active_encounter = user.current_encounter(
        generate_failsafe_if_missing=False)
    if not active_encounter:
        current_app.logger.debug(
            "No current encounter found for user %d, initiate as %s", user.id,
            auth_method)
        initiate_encounter(user, auth_method)
    elif auth_method and active_encounter.auth_method != auth_method:
        current_app.logger.debug(
            "Active encounter has different auth_method: %s; "
            "Starting new with %s", active_encounter.auth_method, auth_method)
        initiate_encounter(user, auth_method)

    # remove session var used to capture locale_code prior to login, now
    # that we have a user.
    if 'locale_code' in session:
        del session['locale_code']
