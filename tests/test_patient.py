"""Test module for patient specific APIs"""

from datetime import datetime
import json

from flask_webtest import SessionScope

from portal.date_tools import FHIR_datetime
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.identifier import Identifier, UserIdentifier
from portal.models.reference import Reference
from portal.models.role import ROLE
from portal.models.user import User
from tests import TEST_USER_ID, TEST_USERNAME, TestCase


class TestPatient(TestCase):

    def test_email_search(self):
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.get(
            '/api/patient/', follow_redirects=True,
            query_string={'email': TEST_USERNAME, 'patch_dstu2': True})
        # Known patient should return bundle of one
        assert response.status_code == 200
        assert response.json['resourceType'] == 'Bundle'
        assert response.json['total'] == 1
        assert (
            response.json['entry'][0]['resource'] ==
            Reference.patient(TEST_USER_ID).as_fhir())

    def test_email_search_old_format(self):
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.get(
            '/api/patient?email={}'.format(TEST_USERNAME),
            follow_redirects=True)
        # Known patient should return bundle of one
        assert response.status_code == 200
        assert response.json['resourceType'] == 'Patient'

    def test_email_search_non_patient(self):
        self.login()
        response = self.client.get(
            '/api/patient/', follow_redirects=True,
            query_string={'email': TEST_USERNAME, 'patch_dstu2': True})
        # Known patient but w/o patient role should return empty bundle
        assert response.status_code == 200
        assert response.json['resourceType'] == 'Bundle'
        assert response.json['total'] == 0

    def test_email_search_non_patient_old_format(self):
        self.login()
        response = self.client.get(
            '/api/patient?email={}'.format(TEST_USERNAME),
            follow_redirects=True)
        # Known patient but w/o patient role should return 404
        assert response.status_code == 404

    def test_inadequate_perms(self):
        dummy = self.add_user(username='dummy@example.com')
        self.promote_user(user=dummy, role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.get(
            '/api/patient/', follow_redirects=True,
            query_string={'email': 'dummy@example.com', 'patch_dstu2': True})
        # w/o permission, should see empty result set
        assert response.status_code == 200
        assert response.json['resourceType'] == 'Bundle'
        assert response.json['total'] == 0

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
            '/api/patient/', follow_redirects=True,
            query_string={'identifier': json.dumps(ident.as_fhir()),
                          'patch_dstu2': True})
        assert response.status_code == 200
        assert response.json['resourceType'] == 'Bundle'
        assert response.json['total'] == 1
        assert (
            response.json['entry'][0]['resource'] ==
            Reference.patient(TEST_USER_ID).as_fhir())

    def test_ident_pipe_search(self):
        ident = Identifier(system='http://example.com', value='testy')
        ui = UserIdentifier(identifier=ident, user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(ident)
            db.session.add(ui)
            db.session.commit()
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        ident = db.session.merge(ident)
        response = self.client.get('/api/patient/', query_string={
            'identifier': '{}|{}'.format(ident.system, ident.value),
            'patch_dstu2': True},
            follow_redirects=True)
        assert response.status_code == 200
        assert response.json['resourceType'] == 'Bundle'
        assert response.json['total'] == 1
        assert (
            response.json['entry'][0]['resource'] ==
            Reference.patient(TEST_USER_ID).as_fhir())

    def test_multimatch_search(self):
        second = self.add_user(username='second')
        second_id = second.id
        self.promote_user(user=second, role_name=ROLE.PATIENT.value)
        ident = Identifier(system='http://example.com', value='testy')
        ui = UserIdentifier(identifier=ident, user_id=TEST_USER_ID)
        ui2 = UserIdentifier(identifier=ident, user_id=second_id)
        with SessionScope(db):
            db.session.add(ident)
            db.session.add(ui)
            db.session.add(ui2)
            db.session.commit()
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.promote_user(role_name=ROLE.ADMIN.value)  # skip org/staff steps
        self.login()
        ident = db.session.merge(ident)
        response = self.client.get('/api/patient/', query_string={
            'identifier': '{}|{}'.format(ident.system, ident.value),
            'patch_dstu2': True},
            follow_redirects=True)
        assert response.status_code == 200
        assert response.json['resourceType'] == 'Bundle'
        assert response.json['total'] == 2
        assert response.json['type'] == 'searchset'

    def test_multimatch_search_old_format(self):
        second = self.add_user(username='second')
        second_id = second.id
        self.promote_user(user=second, role_name=ROLE.PATIENT.value)
        ident = Identifier(system='http://example.com', value='testy')
        ui = UserIdentifier(identifier=ident, user_id=TEST_USER_ID)
        ui2 = UserIdentifier(identifier=ident, user_id=second_id)
        with SessionScope(db):
            db.session.add(ident)
            db.session.add(ui)
            db.session.add(ui2)
            db.session.commit()
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.promote_user(role_name=ROLE.ADMIN.value)  # skip org/staff steps
        self.login()
        ident = db.session.merge(ident)
        response = self.client.get('/api/patient/', query_string={
            'identifier': '{}|{}'.format(ident.system, ident.value)},
            follow_redirects=True)
        # Multi not supported in old format
        assert response.status_code == 400

    def test_deleted_search(self):
        second = self.add_user(username='second')
        second_id = second.id
        self.promote_user(user=second, role_name=ROLE.PATIENT.value)
        ident = Identifier(system='http://example.com', value='testy')
        ui = UserIdentifier(identifier=ident, user_id=TEST_USER_ID)
        ui2 = UserIdentifier(identifier=ident, user_id=second_id)
        with SessionScope(db):
            db.session.add(ident)
            db.session.add(ui)
            db.session.add(ui2)
            db.session.commit()
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.promote_user(role_name=ROLE.ADMIN.value)  # skip org/staff steps

        # Mark second user as deleted - should therefore be excluded
        second = db.session.merge(second)
        second.deleted = Audit(
            user_id=second_id, subject_id=second_id, comment='deleted')
        with SessionScope(db):
            db.session.commit()

        self.login()
        ident = db.session.merge(ident)
        response = self.client.get('/api/patient/', query_string={
            'identifier': '{}|{}'.format(ident.system, ident.value),
            'patch_dstu2': True},
            follow_redirects=True)
        assert response.status_code == 200
        assert response.json['resourceType'] == 'Bundle'
        assert response.json['total'] == 1
        assert response.json['type'] == 'searchset'
        assert (
            response.json['entry'][0]['resource'] ==
            Reference.patient(TEST_USER_ID).as_fhir())

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
        response = self.client.get('/api/patient/', query_string={
            'identifier': id_str,
            'patch_dstu2': True},
            follow_redirects=True)

        # expect empty bundle
        assert response.status_code == 200
        assert response.json['resourceType'] == 'Bundle'
        assert response.json['total'] == 0

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
        response = self.client.get('/api/patient/', query_string={
            'identifier': 'system"http://example.com",value="testy"',
            'patch_dstu2': True},
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

    def test_deceased_pre_epoch(self):
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        pre_epoch = '1899-01-15 00:09:30'
        data = {'deceasedDateTime': pre_epoch}
        response = self.client.post(
            '/api/patient/{}/deceased'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 400
