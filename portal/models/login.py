"""Module for common login hook"""

from flask import current_app, request, session
from flask_babel import gettext as _
from flask_login import (
    current_user as flask_login_current_user,
    login_user as flask_user_login,
    logout_user as flask_user_logout,
)
from flask_user import _call_or_get

from ..database import db
from .encounter import initiate_encounter
from .role import ROLE


def send_2fa_email(user):
    from .message import EmailMessage  # prevent cycle

    code = user.generate_otp()
    current_app.logger.debug(f"2FA OTP for {user.id}: {code}")
    email = EmailMessage(
        subject=_("TrueNTH Access Code"),
        body=_("Your single-use access code is: %(code)06d<br>Thank you,<br>The TrueNTH Team<br><br>This email has been generated automatically; if you have any questions please contact pcctcironmanregistry@mskcc.org .", code=code),
        recipients=user.email,
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        user_id=user.id)
    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        # Dump to console for easy access
        print(email.body)
    else:
        email.send_message()

    db.session.add(email)
    db.session.commit()


def user_requires_2fa(user, skip_2fa_cookie):
    """Logic to determine if user requires 2FA at this time"""
    assert user
    if skip_2fa_cookie and skip_2fa_cookie == user.remember_me_cookie:
        return False

    return (
        current_app.config.get("ENABLE_2FA") and
        not current_app.testing and
        not getattr(getattr(request, 'oauth', None), 'user', None) and
        not user.has_role(ROLE.WRITE_ONLY.value) and
        user.has_role(
                ROLE.ADMIN.value,
                ROLE.ANALYST.value,
                ROLE.CLINICIAN.value,
                ROLE.PRIMARY_INVESTIGATOR.value,
                ROLE.CLINICIAN.value,
                ROLE.RESEARCHER.value,
                ROLE.STAFF.value,
                ROLE.STAFF_ADMIN.value,
        ) and
        session.get('2FA_verified') != '2FA verified')


def login_user(user, auth_method=None):
    """Common entry point for all login flows - direct here for bookkeeping

    :param user: The user to log in
    :param auth_method: If known, the method used to log in.

    Logs user into flask_user system and generates the encounter used to track
    authentication method.

    """
    # beyond patients and caregivers, 2FA is required.  confirm or initiate
    skip_2fa_cookie = request.cookies.get("Truenth2FA_REMEMBERME")
    if user_requires_2fa(user, skip_2fa_cookie):
        # log user back out, in case a flow already promoted them
        flask_user_logout()

        session['user_needing_2fa'] = user.id
        session['pending_auth_method'] = auth_method
        send_2fa_email(user)
        return

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

    # retain skip 2fa cookie value for subsequent login comparison (if set)
    if skip_2fa_cookie:
        user.remember_me_cookie = skip_2fa_cookie
        db.session.commit()
