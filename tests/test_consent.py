"""Unit test module for user consent"""
from flask_webtest import SessionScope
import json

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.organization import Organization
from portal.models.user_consent import UserConsent
from tests import TestCase, TEST_USER_ID


class TestUserConsent(TestCase):
    url = 'http://fake.com?arg=critical'

    def test_user_consent(self):
        org1 = Organization(name='test_1')
        org2 = Organization(name='test_2')

        audit = Audit(user_id=TEST_USER_ID)
        uc1 = UserConsent(organization=org1, agreement_url=self.url,
                          audit=audit)
        uc2 = UserConsent(organization=org2, agreement_url=self.url,
                          audit=audit)
        self.test_user.consents.append(uc1)
        self.test_user.consents.append(uc2)
        with SessionScope(db):
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        self.login()
        rv = self.app.get('/api/user/{}/consent'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(len(rv.json['consent_agreements']), 2)

    def test_post_user_consent(self):
        org1 = Organization(name='test_1')
        with SessionScope(db):
            db.session.add(org1)
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        org1 = db.session.merge(org1)

        data = {'organization_id': org1.id, 'agreement_url': self.url}

        self.login()
        rv = self.app.post('/api/user/{}/consent'.format(TEST_USER_ID),
                          content_type='application/json',
                          data=json.dumps(data))
        self.assert200(rv)
        self.assertEqual(self.test_user.consents.count(), 1)
        self.assertEqual(self.test_user.consents[0].organization_id, org1.id)
