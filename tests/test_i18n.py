"""Unit test module for internationalization logic"""
import sys

from flask import current_app
from flask_login import login_user
import pytest

from portal.models.i18n import get_locale
from portal.models.user import User
from tests import TEST_USER_ID, TestCase

if sys.version_info.major > 2:
    pytest.skip(msg="not yet ported to python3", allow_module_level=True)
class TestI18n(TestCase):
    """I18n tests"""

    def test_get_locale(self):
        self.assertEqual(
            get_locale(), current_app.config.get("DEFAULT_LOCALE"))

        language = 'en_AU'
        language_name = "Australian English"

        test_user = User.query.get(TEST_USER_ID)
        test_user.locale = (language, language_name)

        login_user(test_user)
        self.assertEqual(get_locale(), language)
