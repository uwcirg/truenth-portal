"""Test module for audit functionality"""
from dateutil import parser
from flask.ext.webtest import SessionScope
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.reference import Reference
from portal.models.role import ROLE

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

    def test_empty(self):
        "no audit for user should still function"
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.app.get('/api/user/{}/audit'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(0, len(rv.json['audits']))

    def test_get(self):
        audit = Audit(user_id=TEST_USER_ID, comment='just test data')
        with SessionScope(db):
            db.session.add(audit)
            db.session.commit()

        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.app.get('/api/user/{}/audit'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(1, len(rv.json['audits']))
        self.assertEquals(rv.json['audits'][0]['by'],
                          Reference.patient(TEST_USER_ID).as_fhir())
        self.assertEquals(
            rv.json['audits'][0]['comment'], 'just test data')
