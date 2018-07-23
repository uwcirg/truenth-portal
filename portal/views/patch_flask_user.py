"""workarounds to flask_user problems"""
from __future__ import unicode_literals  # isort:skip
from future import standard_library # isort:skip
standard_library.install_aliases()  # noqa: E402

from urllib.parse import urlsplit, urlunsplit

from flask import current_app, flash, redirect, request, url_for
from flask_babel import force_locale, gettext as _
from flask_user.views import _endpoint_url


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
        return redirect(_endpoint_url(user_manager.after_forgot_password_endpoint))

    # Process GET or invalid POST
    return user_manager.render_function(
        user_manager.forgot_password_template, form=form)
