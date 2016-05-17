"""Test module for audit functionality"""
from dateutil import parser
from tests import TestCase, TEST_USER_ID
from portal.models.audit import Audit

log_login_idp = "2016-02-23 09:49:25,733: {} performed: login user via NEW IdP facebook".format(TEST_USER_ID)
log_login_google = "2016-02-23 09:52:57,806: {} performed: login via google".format(TEST_USER_ID)
log_callbacks = """2016-02-23 10:52:24,856: {} performed: after: Client: yoOjy6poL2dVPVcXgi7zc8gCS0qvnOzpwyQemCTw, redirects: https://stg-sr.us.truenth.org/, callback: https://stg-sr.us.truenth.org/_/callback""".format(TEST_USER_ID)

class TestAudit(TestCase):
    """Audit model tests"""

    def test_parse_user(self):
        a1 = Audit.from_logentry(log_login_idp)
        self.assertEquals(a1.user_id, TEST_USER_ID)

    def test_message(self):
        a1 = Audit.from_logentry(log_callbacks)
        expected = """ after: Client: yoOjy6poL2dVPVcXgi7zc8gCS0qvnOzpwyQemCTw, redirects: https://stg-sr.us.truenth.org/, callback: https://stg-sr.us.truenth.org/_/callback"""
        self.assertEquals(a1.comment, expected)

    def test_parse_timezone(self):
        a1 = Audit.from_logentry(log_login_google)
        expected = parser.parse("2016-02-23 09:52")
        self.assertEquals(a1.timestamp, expected)
