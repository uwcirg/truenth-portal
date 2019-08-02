"""Unit test module for internationalization logic"""

from flask import current_app
from flask_login import login_user

from portal.models.i18n import get_locale
from portal.models.user import User
from tests import TEST_USER_ID, TestCase


class TestI18n(TestCase):
    """I18n tests"""

    def test_get_locale(self):
        assert get_locale() == current_app.config.get("DEFAULT_LOCALE")

        language = 'en_AU'
        language_name = "Australian English"

        test_user = User.query.get(TEST_USER_ID)
        test_user.locale = (language, language_name)

        login_user(test_user)
        assert get_locale() == language
