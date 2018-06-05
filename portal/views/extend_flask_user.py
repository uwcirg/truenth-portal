"""Module to extend or specialize flask user views for our needs"""
from flask import abort, current_app, session, url_for
from flask_user.views import reset_password

from ..models.role import ROLE
from ..models.user import get_user_or_abort
from .portal import challenge_identity


def reset_password_view_function(token):
    """Extend the flask_user view function to include challenge questions"""
    is_valid, has_expired, user_id = current_app.user_manager.verify_token(
        token,
        current_app.user_manager.reset_password_expiration)
    user = get_user_or_abort(user_id)

    # as this is an entry point for not-yet-logged-in users, capture their
    # locale_code in the session for template rendering prior to logging in.
    # (Post log-in, the current_user().locale_code is always available
    session['locale_code'] = user.locale_code

    if current_app.config.get("NO_CHALLENGE_WO_DATA"):
        # Some early users were not forced to set DOB and name fields.
        # As they will fail the challenge without data to compare, provide
        # a back door.
        if not all((user.birthdate, user.first_name, user.last_name)):
            if user.has_role(ROLE.ACCESS_ON_VERIFY):
                message = (
                    "User missing required verify attribute not allowed "
                    "to bypass verify on p/w reset")
                current_app.logger.error(message)
                abort(403, message)
            return reset_password(token)

    # Once the user has passed the challenge, let the flask_user
    # reset_password() function to the real work
    verified = session.get('challenge_verified_user_id')
    if verified and verified == user_id:
        return reset_password(token)

    next_url = url_for('user.reset_password', token=token)
    return challenge_identity(user_id=user_id, next_url=next_url)
