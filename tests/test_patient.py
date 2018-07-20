"""Test module for patient specific APIs"""
from __future__ import unicode_literals  # isort:skip

from datetime import datetime
import json

from flask_webtest import SessionScope

from portal.date_tools import FHIR_datetime
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.identifier import Identifier, UserIdentifier
from portal.models.role import ROLE
from portal.models.user import User
from tests import TEST_USER_ID, TEST_USERNAME, TestCase


class TestPatient(TestCase):

    def test_email_search(self):
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.get(
            '/api/patient?email={}'.format(TEST_USERNAME),
            follow_redirects=True)
        # Known patient but w/o patient role should 404
        assert response.status_code == 200
        assert response.json['resourceType'] == 'Patient'

    def test_email_search_non_patient(self):
        self.login()
        response = self.client.get(
            '/api/patient?email={}'.format(TEST_USERNAME),
            follow_redirects=True)
        # Known patient but w/o patient role should 404
        assert response.status_code == 404

    def test_inadequate_perms(self):
        dummy = self.add_user(username='dummy@example.com')
        self.promote_user(user=dummy, role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.get(
            '/api/patient?email={}'.format('dummy@example.com'),
            follow_redirects=True)
        # w/o permission, should see a 404 not a 401 on search
        assert response.status_code == 404

    def test_ident_search(self):
        ident = Identifier(system='http://example.com', value='testy')
        ui = UserIdentifier(identifier=ident, user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(ident)
            db.session.add(ui)
            db.session.commit()
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        ident = db.session.merge(ident)
        response = self.client.get(
            '/api/patient?identifier={}'.format(json.dumps(ident.as_fhir())),
            follow_redirects=True)
        assert response.status_code == 200

    def test_ident_nomatch_search(self):
        ident = Identifier(system='http://example.com', value='testy')
        ui = UserIdentifier(identifier=ident, user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(ident)
            db.session.add(ui)
            db.session.commit()
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        ident = db.session.merge(ident)
        # modify the system to mis match
        id_str = json.dumps(ident.as_fhir()).replace(
            "example.com", "wrong-system.com")
        response = self.client.get(
            '/api/patient?identifier={}'.format(id_str),
            follow_redirects=True)
        assert response.status_code == 404

    def test_ill_formed_ident_search(self):
        ident = Identifier(system='http://example.com', value='testy')
        ui = UserIdentifier(identifier=ident, user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(ident)
            db.session.add(ui)
            db.session.commit()
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        ident = db.session.merge(ident)
        response = self.client.get(
            '/api/patient?identifier=system"http://example.com",value="testy"',
            follow_redirects=True)
        assert response.status_code == 400

    def test_birthDate(self):
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        data = {'birthDate': '1976-07-04'}
        response = self.client.post(
            '/api/patient/{}/birthDate'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200
        user = User.query.get(TEST_USER_ID)
        assert user.birthdate
        assert user.birthdate.strftime("%Y-%m-%d") == "1976-07-04"

    def test_deceased(self):
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        now = FHIR_datetime.as_fhir(datetime.utcnow())
        data = {'deceasedDateTime': now}
        response = self.client.post(
            '/api/patient/{}/deceased'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200
        user = User.query.get(TEST_USER_ID)
        assert user.deceased

    def test_deceased_undead(self):
        """POST should allow reversal if already deceased"""
        self.promote_user(role_name=ROLE.PATIENT.value)
        d_audit = Audit(
            user_id=TEST_USER_ID, subject_id=TEST_USER_ID, context='user',
            comment="time of death for user {}".format(TEST_USER_ID))
        with SessionScope(db):
            db.session.add(d_audit)
            db.session.commit()
        self.test_user, d_audit = map(
            db.session.merge, (self.test_user, d_audit))
        self.test_user.deceased = d_audit
        self.login()
        data = {'deceasedBoolean': False}
        response = self.client.post(
            '/api/patient/{}/deceased'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200
        patient = User.query.get(TEST_USER_ID)
        assert not patient.deceased
