"""Test identifiers"""
import json
from flask_webtest import SessionScope
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.identifier import Identifier
from portal.models.user import User


class TestIdentifier(TestCase):

    def testGET(self):
        expected = len(self.test_user.identifiers)
        self.login()
        rv = self.client.get('/api/user/{}/identifier'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEqual(len(rv.json['identifier']), expected)

    def testPOST(self):
        """Add an existing and fresh identifier - confirm it sticks"""
        expected = len(self.test_user.identifiers) + 2
        existing = Identifier(system='http://notreal.com', value='unique')
        with SessionScope(db):
            db.session.add(existing)
            db.session.commit()
        existing = db.session.merge(existing)
        fresh = Identifier(system='http://another.com', value='unique')
        data = {'identifier': [i.as_fhir() for i in (existing, fresh)]}
        self.login()
        rv = self.client.post(
            '/api/user/{}/identifier'.format(TEST_USER_ID),
            content_type='application/json', data=json.dumps(data))
        self.assert200(rv)
        self.assertEqual(len(rv.json['identifier']), expected)
        user = User.query.get(TEST_USER_ID)
        self.assertEqual(len(user.identifiers), expected)
