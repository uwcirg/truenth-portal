"""Unit test module for user consent"""
from __future__ import unicode_literals  # isort:skip

from datetime import datetime
from dateutil.relativedelta import relativedelta
import json

from dateutil import parser
from flask import current_app
from flask_webtest import SessionScope

from portal.date_tools import FHIR_datetime
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.organization import Organization
from portal.models.user_consent import UserConsent
from tests import TEST_USER_ID, TestCase


class TestUserConsent(TestCase):
    url = 'http://fake.com?arg=critical'

    def test_content_options(self):
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        self.shallow_org_tree()
        org1, _ = [org for org in Organization.query.filter(
            Organization.id > 0).limit(2)]
        uc = UserConsent(
            user_id=TEST_USER_ID, organization=org1,
            audit=audit, agreement_url='http://no.com')
        uc.include_in_reports = True
        with SessionScope(db):
            db.session.add(uc)
            db.session.commit()

        uc = UserConsent.query.first()
        assert uc.include_in_reports
        assert not uc.staff_editable
        assert not uc.send_reminders

    def test_user_consent(self):
        self.shallow_org_tree()
        org1, org2 = [org for org in Organization.query.filter(
            Organization.id > 0).limit(2)]

        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc1 = UserConsent(
            organization_id=org1.id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit)
        uc2 = UserConsent(
            organization_id=org2.id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit)
        uc1.staff_editable = True
        uc1.send_reminders = False
        uc2.staff_editable = True
        uc2.send_reminders = False
        uc2.status = 'suspended'
        with SessionScope(db):
            db.session.add(uc1)
            db.session.add(uc2)
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        self.login()
        response = self.client.get('/api/user/{}/consent'.format(TEST_USER_ID))
        assert response.status_code == 200
        assert len(response.json['consent_agreements']) == 2
        assert 'send_reminders' not in response.json['consent_agreements'][0]
        assert 'staff_editable' in response.json['consent_agreements'][0]
        org1, org2 = db.session.merge(org1), db.session.merge(org2)
        org1_consent = [ca for ca in response.json[
            'consent_agreements'] if ca['organization_id'] == org1.id][0]
        org2_consent = [ca for ca in response.json[
            'consent_agreements'] if ca['organization_id'] == org2.id][0]
        assert org1_consent['status'] == 'consented'
        assert org2_consent['status'] == 'suspended'

    def test_consent_order(self):
        self.shallow_org_tree()
        org1, org2 = [org for org in Organization.query.filter(
            Organization.id > 0).limit(2)]
        old = datetime.now() - relativedelta(years=10)
        older = old - relativedelta(years=10)
        oldest = older - relativedelta(years=50)

        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc1 = UserConsent(
            organization_id=org1.id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit, acceptance_date=older)
        uc2 = UserConsent(
            organization_id=org2.id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit, acceptance_date=oldest)
        uc3 = UserConsent(
            organization_id=0, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit, acceptance_date=old)
        with SessionScope(db):
            db.session.add(uc1)
            db.session.add(uc2)
            db.session.add(uc3)
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        self.login()
        response = self.client.get(
            '/api/user/{}/consent'.format(TEST_USER_ID))
        assert response.status_code == 200
        assert len(response.json['consent_agreements']) == 3
        # should be ordered by acceptance date, descending: (uc3, uc1, uc2)
        uc1, uc2, uc3 = map(db.session.merge, (uc1, uc2, uc3))
        assert response.json['consent_agreements'][0] == uc3.as_json()
        assert response.json['consent_agreements'][1] == uc1.as_json()
        assert response.json['consent_agreements'][2] == uc2.as_json()

    def test_post_user_consent(self):
        self.shallow_org_tree()
        org1 = Organization.query.filter(Organization.id > 0).first()
        data = {'organization_id': org1.id, 'agreement_url': self.url,
                'staff_editable': True, 'send_reminders': False}

        self.login()
        response = self.client.post(
            '/api/user/{}/consent'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.valid_consents.count() == 1
        consent = self.test_user.valid_consents[0]
        assert consent.organization_id, org1.id
        assert consent.staff_editable
        assert not consent.send_reminders

    def test_post_user_consent_dates(self):
        self.shallow_org_tree()
        org1 = Organization.query.filter(Organization.id > 0).first()
        acceptance_date = "2007-10-30"
        data = {'organization_id': org1.id,
                'agreement_url': self.url,
                'acceptance_date': acceptance_date}

        self.login()
        response = self.client.post(
            '/api/user/{}/consent'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.valid_consents.count() == 1
        consent = self.test_user.valid_consents[0]
        assert consent.organization_id == org1.id
        assert consent.acceptance_date == parser.parse(acceptance_date)
        assert (
            consent.audit.comment ==
            "Consent agreement {} signed".format(consent.id))
        assert (datetime.utcnow() - consent.audit.timestamp).seconds < 30

    def test_post_multi_user_consent_dates(self):
        """Confirm default "now" isn't stuck in time"""
        self.shallow_org_tree()
        org1 = Organization.query.filter(Organization.id > 0).first()
        data = {'organization_id': org1.id,
                'agreement_url': self.url,}
        self.login()
        response = self.client.post(
            '/api/user/{}/consent'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.valid_consents.count() == 1
        consent = self.test_user.valid_consents[0]
        assert consent.organization_id == org1.id
        assert (
            consent.audit.comment ==
            "Consent agreement {} signed".format(consent.id))
        assert (datetime.utcnow() - consent.audit.timestamp).seconds < 30
        first_user_acceptance_date = consent.acceptance_date

        # now add second, confirm time moved
        second_user = self.add_user('second')
        self.login(user_id=second_user.id)
        response = self.client.post(
            '/api/user/{}/consent'.format(second_user.id),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200
        second_user = db.session.merge(second_user)
        assert second_user.valid_consents.count() == 1
        consent = second_user.valid_consents[0]
        assert first_user_acceptance_date != consent.acceptance_date

    def test_post_user_future_consent_date(self):
        """Shouldn't allow future consent date"""
        self.shallow_org_tree()
        org1 = Organization.query.filter(Organization.id > 0).first()
        acceptance_date = datetime.utcnow() + relativedelta(days=1)
        data = {'organization_id': org1.id,
                'agreement_url': self.url,
                'acceptance_date': FHIR_datetime.as_fhir(acceptance_date)}

        self.login()
        response = self.client.post(
            '/api/user/{}/consent'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 400

    def test_post_replace_user_consent(self):
        """second consent for same user,org should replace existing"""
        self.shallow_org_tree()
        org1 = Organization.query.filter(Organization.id > 0).first()
        data = {'organization_id': org1.id, 'agreement_url': self.url,
                'staff_editable': True, 'send_reminders': True}

        self.login()
        response = self.client.post(
            '/api/user/{}/consent'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.valid_consents.count() == 1
        consent = self.test_user.valid_consents[0]
        assert consent.organization_id == org1.id
        assert consent.staff_editable
        assert consent.send_reminders
        assert consent.status == 'consented'

        # modify flags & repost - should have new values and only one
        data['staff_editable'] = False
        data['send_reminders'] = False
        data['status'] = 'suspended'
        response = self.client.post(
            '/api/user/{}/consent'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200
        assert self.test_user.valid_consents.count() == 1
        consent = self.test_user.valid_consents[0]
        assert consent.organization_id == org1.id
        assert not consent.staff_editable
        assert not consent.send_reminders
        assert consent.status == 'suspended'

        dc = UserConsent.query.filter_by(user_id=TEST_USER_ID,
                                         organization_id=org1.id,
                                         status='deleted').first()
        assert dc.deleted_id

    def test_delete_user_consent(self):
        self.shallow_org_tree()
        org1, org2 = [org for org in Organization.query.filter(
            Organization.id > 0).limit(2)]
        org1_id, org2_id = org1.id, org2.id
        data = {'organization_id': org1_id}

        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc1 = UserConsent(
            organization_id=org1_id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit)
        uc2 = UserConsent(
            organization_id=org2_id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit)
        with SessionScope(db):
            db.session.add(uc1)
            db.session.add(uc2)
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.valid_consents.count() == 2
        self.login()

        response = self.client.delete(
            '/api/user/{}/consent'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200
        assert self.test_user.valid_consents.count() == 1
        assert self.test_user.valid_consents[0].organization_id == org2_id

        # We no longer omit deleted consent rows, but rather, include
        # their audit data.
        response = self.client.get('/api/user/{}/consent'.format(TEST_USER_ID))
        assert 'deleted' in json.dumps(response.json)

        # confirm deleted status
        dc = UserConsent.query.filter_by(
            user_id=TEST_USER_ID, organization_id=org1_id).first()
        assert dc.status == 'deleted'

    def test_withdraw_user_consent(self):
        self.shallow_org_tree()
        org = Organization.query.filter(Organization.id > 0).first()
        org_id = org.id

        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc = UserConsent(
            organization_id=org_id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit)
        with SessionScope(db):
            db.session.add(uc)
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.valid_consents.count() == 1

        data = {'organization_id': org_id}
        self.login()
        resp = self.client.post(
            '/api/user/{}/consent/withdraw'.format(TEST_USER_ID),
            content_type='application/json', data=json.dumps(data))
        assert resp.status_code == 200

        # check that old consent is marked as deleted
        old_consent = UserConsent.query.filter_by(
            user_id=TEST_USER_ID, organization_id=org_id,
            status='deleted').first()
        assert old_consent.deleted_id

        # check new withdrawn consent
        new_consent = UserConsent.query.filter_by(
            user_id=TEST_USER_ID, organization_id=org_id,
            status='suspended').first()
        assert old_consent.agreement_url == new_consent.agreement_url
        assert (
            new_consent.staff_editable ==
            (not current_app.config.get('GIL')))
        assert not new_consent.send_reminders
