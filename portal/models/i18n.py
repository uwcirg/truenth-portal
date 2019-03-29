"""Module for i18n methods and functionality"""
from __future__ import unicode_literals  # isort:skip
from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402

from collections import defaultdict
from io import BytesIO
import os
import re
import sys
import tempfile

from babel import negotiate_locale
from flask import current_app, has_request_context, request, session
from polib import pofile
import requests

from ..extensions import babel
from ..system_uri import IETF_LANGUAGE_TAG
from .app_text import AppText
from .coding import Coding
from .intervention import Intervention
from .organization import Organization
from .questionnaire_bank import QuestionnaireBank, classification_types_enum
from .research_protocol import ResearchProtocol
from .role import Role
from .user import current_user


def get_db_strings():
    msgid_map = defaultdict(set)
    i18n_fields = {
        AppText: ('custom_text',),
        Intervention: ('description', 'card_html'),
        Organization: ('name',),
        QuestionnaireBank: ('display_name',),
        ResearchProtocol: ('display_name',),
        Role: ('display_name',)
    }

    for model, fields in i18n_fields.items():
        for entry in model.query:
            for field_name in fields:
                msgid = getattr(entry, field_name)
                if not msgid:
                    continue
                msgid = '"{}"'.format(re.sub('"', r'\\"', msgid))
                msgid_map[msgid].add("{model_name}: {field_ref}".format(
                    model_name=model.__name__,
                    field_ref=entry.name,
                ))
    return msgid_map


def get_static_strings():
    """Manually add strings that are otherwise difficult to extract"""
    msgid_map = {}
    status_strings = (
        'Completed',
        'Due',
        'In Progress',
        'Overdue',
        'Expired',
    )
    msgid_map.update({
        '"{}"'.format(s):
            {'assessment_status: %s' % s} for s in status_strings
    })

    enum_options = {
        classification_types_enum: ('title',),
    }
    for enum, options in enum_options.items():
        for value in enum.enums:
            for function_name in options:
                value = getattr(value, function_name)()
            msgid_map['"{}"'.format(value)] = {'{}: {}'.format(
                enum.name, value)}
    return msgid_map


@babel.localeselector
def get_locale():
    if current_user() and current_user().locale_code:
        return current_user().locale_code

    # look for session variable in pre-logged-in state
    # confirm request context - not available from celery tasks
    if has_request_context():
        if session.get('locale_code'):
            return session['locale_code']
        browser_pref = negotiate_locale(
            preferred=(
                l.replace('-', '_') for l in request.accept_languages.values()
            ),
            available=(
                c.code for c in Coding.query.filter_by(system=IETF_LANGUAGE_TAG)
            ),
        )
        if browser_pref:
            return browser_pref
    return current_app.config.get("DEFAULT_LOCALE")
