"""Test module for audit functionality"""
from dateutil import parser
from flask_webtest import SessionScope
from tests import TestCase, TEST_USER_ID, FIRST_NAME, LAST_NAME

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.organization import Organization
from portal.models.reference import Reference
from portal.models.role import ROLE
from portal.models.user_consent import UserConsent

log_login_idp = "2016-02-23 09:49:25,733: performed by {} on {}: login: login user via NEW IdP facebook".format(TEST_USER_ID,TEST_USER_ID)
log_login_google = "2016-02-23 09:52:57,806: performed by {} on {}: login: login via google".format(TEST_USER_ID,TEST_USER_ID)
log_callbacks = """2016-02-23 10:52:24,856: performed by {} on {}: other: after: Client: yoOjy6poL2dVPVcXgi7zc8gCS0qvnOzpwyQemCTw, redirects: https://stg-sr.us.truenth.org/, callback: https://stg-sr.us.truenth.org/_/callback""".format(TEST_USER_ID,TEST_USER_ID)

class TestAudit(TestCase):
    """Audit model tests"""

    def test_parse_user(self):
        a1 = Audit.from_logentry(log_login_idp)
        self.assertEquals(a1.user_id, TEST_USER_ID)

    def test_parse_subject(self):
        a1 = Audit.from_logentry(log_login_idp)
        self.assertEquals(a1.subject_id, TEST_USER_ID)

    def test_parse_context(self):
        a1 = Audit.from_logentry(log_login_idp)
        self.assertEquals(a1.context, "login")

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
        rv = self.client.get('/api/user/{}/audit'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(0, len(rv.json['audits']))

    def test_get(self):
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID,
                        comment='just test data')
        with SessionScope(db):
            db.session.add(audit)
            db.session.commit()

        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.client.get('/api/user/{}/audit'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(1, len(rv.json['audits']))
        self.assertEquals(
            rv.json['audits'][0]['by']['reference'],
            Reference.patient(TEST_USER_ID).as_fhir()['reference'])
        self.assertEquals(
            rv.json['audits'][0]['by']['display'],
            ' '.join((FIRST_NAME, LAST_NAME)))
        self.assertEquals(rv.json['audits'][0]['on'],
                          Reference.patient(TEST_USER_ID).as_fhir())
        self.assertEquals(rv.json['audits'][0]['context'], 'other')
        self.assertEquals(
            rv.json['audits'][0]['comment'], 'just test data')

    def test_staff_access(self):
        staff = self.add_user('provider@example.com')
        self.promote_user(role_name=ROLE.PATIENT)
        self.promote_user(staff, role_name=ROLE.STAFF)
        self.shallow_org_tree()
        org = Organization.query.filter(Organization.id > 0).first()
        staff.organizations.append(org)
        self.test_user.organizations.append(org)
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID,
                    comment='just test data')
        consent = UserConsent(user_id=TEST_USER_ID, organization_id=org.id,
                              audit=audit, agreement_url='http://fake.org')
        with SessionScope(db):
            db.session.add(audit)
            db.session.add(consent)
            db.session.commit()
        staff = db.session.merge(staff)
        self.login(staff.id)
        rv = self.client.get('/api/user/{}/audit'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(1, len(rv.json['audits']))
        self.assertEquals(
            rv.json['audits'][0]['by']['reference'],
            Reference.patient(TEST_USER_ID).as_fhir()['reference'])
        self.assertEquals(rv.json['audits'][0]['on'],
                          Reference.patient(TEST_USER_ID).as_fhir())
        self.assertEquals(rv.json['audits'][0]['context'], 'other')
        self.assertEquals(
            rv.json['audits'][0]['comment'], 'just test data')
