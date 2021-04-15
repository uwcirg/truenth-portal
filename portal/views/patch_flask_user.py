"""workarounds to flask_user problems"""


from urllib.parse import urlsplit, urlunsplit

from flask import current_app, flash, redirect, request, session, url_for
from flask_babel import force_locale, gettext as _
from flask_user.views import _endpoint_url

from ..database import db
from ..models.message import EmailMessage
from ..models.user import current_user


def patch_make_safe_url(url):
    """Patch flask_user.make_safe_url() to include '?'

    Turns an unsafe absolute URL into a safe relative URL by removing
    the scheme and the hostname
    Example:
        make_safe_url('http://hostname/path1/path2?q1=v1&q2=v2#fragment')
        returns: '/path1/path2?q1=v1&q2=v2#fragment

    """
    parts = urlsplit(url)
    no_scheme, no_hostname = '', ''
    safe_url = urlunsplit(
        (no_scheme, no_hostname, parts.path, parts.query, parts.fragment))

    if current_app.config.get('ENABLE_2FA'):
        # With 2FA enabled, can't simply redirect to `safe_url` after login,
        # as 2FA hasn't yet been satisfied, i.e. heading straight to desired
        # target, aka `safe_url` will circumvent the 2FA challenge.

        # Prepend the configured after login endpoint as the "safe_url" for 2FA
        # flow, including the user's desired target as a `next` parameter
        after_login_endpoint = url_for(
            current_app.config['USER_AFTER_LOGIN_ENDPOINT'])
        if not safe_url.startswith(after_login_endpoint):
            # Necessary to avoid chaining during multiple redirects, only
            # prepend configured after login endpoint if not already present
            safe_url = url_for(
                current_app.config['USER_AFTER_LOGIN_ENDPOINT'], next=safe_url)
        return safe_url

    return safe_url


def patch_forgot_password():
    """Need to customize flash message shown in forgot_password

    No hooks available to customize the message, so this function is
    intended to be a drop in replacement with only the text of the
    message altered, as per TN-1030

    """
    """Prompt for email and send reset password email."""
    user_manager = current_app.user_manager

    # Initialize form
    form = user_manager.forgot_password_form(request.form)

    # Process valid POST
    if request.method == 'POST' and form.validate():
        email = form.email.data
        user, user_email = user_manager.find_user_by_email(email)

        if user:
            with force_locale(user.locale_code):
                user_manager.send_reset_password_email(email)

        # Prepare one-time system message
        flash(_("If the email address '%(email)s' is in the system, a "
                "reset password email will now have been sent to it. "
                "Please open that email and follow the instructions to "
                "reset your password.", email=email), 'success')

        # Redirect to the login page
        return redirect(
            _endpoint_url(user_manager.after_forgot_password_endpoint))

    # Process GET or invalid POST
    return user_manager.render_function(
        user_manager.forgot_password_template, form=form)


def patch_send_email(recipient, subject, html_message, text_message):
    """ Replace flask_user's `send_email` for tracking purposes

    In order to capture emails sent by flask-user, replicate and customize
    the built in flask_user function.

    """

    # Disable email sending when testing
    if current_app.testing:
        return

    user = current_user()
    user_id = user.id if user else None
    email = EmailMessage(
        subject=subject, body=html_message, recipients=recipient,
        sender=current_app.config['MAIL_DEFAULT_SENDER'], user_id=user_id)

    email.send_message()
    db.session.add(email)
    db.session.commit()
