"""Module to extend or specialize flask user views for our needs"""
from flask import current_app, url_for, session
from flask_user.views import reset_password

from .portal import challenge_identity


def reset_password_view_function(token):
    """Extend the flask_user view function to include challenge questions"""
    is_valid, has_expired, user_id = current_app.user_manager.verify_token(
        token,
        current_app.user_manager.reset_password_expiration)

    # Once the user has passed the challenge, let the flask_user
    # reset_password() function to the real work
    verified = session.get('challenge_verified_user_id')
    if verified and verified == user_id:
        return reset_password(token)

    next_url = url_for('user.reset_password', token=token)
    return challenge_identity(user_id=user_id, next_url=next_url)
