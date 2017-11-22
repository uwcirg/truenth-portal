"""Unit test module for user consent"""
from dateutil import parser
from flask_webtest import SessionScope
import json

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.organization import Organization
from portal.models.user_consent import UserConsent
from tests import TestCase, TEST_USER_ID


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
        self.assertTrue(uc.include_in_reports)
        self.assertFalse(uc.staff_editable)
        self.assertFalse(uc.send_reminders)

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
        rv = self.client.get('/api/user/{}/consent'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(len(rv.json['consent_agreements']), 2)
        self.assertTrue('send_reminders' not in
                        rv.json['consent_agreements'][0])
        self.assertTrue('staff_editable' in
                        rv.json['consent_agreements'][0])
        self.assertEquals(rv.json['consent_agreements'][0]['status'],
                          'consented')
        self.assertEquals(rv.json['consent_agreements'][1]['status'],
                          'suspended')

    def test_post_user_consent(self):
        self.shallow_org_tree()
        org1 = Organization.query.filter(Organization.id > 0).first()
        data = {'organization_id': org1.id, 'agreement_url': self.url,
                'staff_editable': True, 'send_reminders': False}

        self.login()
        rv = self.client.post('/api/user/{}/consent'.format(TEST_USER_ID),
                          content_type='application/json',
                          data=json.dumps(data))
        self.assert200(rv)
        self.test_user = db.session.merge(self.test_user)
        self.assertEqual(self.test_user.valid_consents.count(), 1)
        consent = self.test_user.valid_consents[0]
        self.assertEqual(consent.organization_id, org1.id)
        self.assertTrue(consent.staff_editable)
        self.assertFalse(consent.send_reminders)

    def test_post_user_consent_dates(self):
        self.shallow_org_tree()
        org1 = Organization.query.filter(Organization.id > 0).first()
        acceptance_date = "2007-10-30"
        data = {'organization_id': org1.id,
                'agreement_url': self.url,
                'acceptance_date': acceptance_date}

        self.login()
        rv = self.client.post('/api/user/{}/consent'.format(TEST_USER_ID),
                          content_type='application/json',
                          data=json.dumps(data))
        self.assert200(rv)
        self.test_user = db.session.merge(self.test_user)
        self.assertEqual(self.test_user.valid_consents.count(), 1)
        self.assertEqual(self.test_user.valid_consents[0].organization_id,
                         org1.id)
        self.assertEqual(self.test_user.valid_consents[0].audit.timestamp,
                         parser.parse(acceptance_date))

    def test_post_replace_user_consent(self):
        """second consent for same user,org should replace existing"""
        self.shallow_org_tree()
        org1 = Organization.query.filter(Organization.id > 0).first()
        data = {'organization_id': org1.id, 'agreement_url': self.url,
                'staff_editable': True, 'send_reminders': True}

        self.login()
        rv = self.client.post('/api/user/{}/consent'.format(TEST_USER_ID),
                              content_type='application/json',
                              data=json.dumps(data))
        self.assert200(rv)
        self.test_user = db.session.merge(self.test_user)
        self.assertEqual(self.test_user.valid_consents.count(), 1)
        consent = self.test_user.valid_consents[0]
        self.assertEqual(consent.organization_id, org1.id)
        self.assertTrue(consent.staff_editable)
        self.assertTrue(consent.send_reminders)
        self.assertEqual(consent.status, 'consented')

        # modify flags & repost - should have new values and only one
        data['staff_editable'] = False
        data['send_reminders'] = False
        data['status'] = 'suspended'
        rv = self.client.post('/api/user/{}/consent'.format(TEST_USER_ID),
                              content_type='application/json',
                              data=json.dumps(data))
        self.assert200(rv)
        self.assertEqual(self.test_user.valid_consents.count(), 1)
        consent = self.test_user.valid_consents[0]
        self.assertEqual(consent.organization_id, org1.id)
        self.assertFalse(consent.staff_editable)
        self.assertFalse(consent.send_reminders)
        self.assertEqual(consent.status, 'suspended')

        dc = UserConsent.query.filter_by(user_id=TEST_USER_ID,
                                         organization_id=org1.id,
                                         status='purged').first()
        self.assertTrue(dc.deleted_id)

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
        self.assertEqual(self.test_user.valid_consents.count(), 2)
        self.login()

        rv = self.client.delete('/api/user/{}/consent'.format(TEST_USER_ID),
                             content_type='application/json',
                             data=json.dumps(data))
        self.assert200(rv)
        self.assertEqual(self.test_user.valid_consents.count(), 1)
        self.assertEqual(self.test_user.valid_consents[0].organization_id,
                         org2_id)

        # We no longer omit deleted consent rows, but rather, include
        # their audit data.
        rv = self.client.get('/api/user/{}/consent'.format(TEST_USER_ID))
        self.assertTrue('deleted' in json.dumps(rv.json))
