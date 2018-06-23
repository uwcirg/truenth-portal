"""Test identifiers"""
import json
import sys

from flask_webtest import SessionScope
import pytest

from portal.extensions import db
from portal.models.identifier import Identifier
from portal.models.user import User
from tests import TEST_USER_ID, TestCase


if sys.version_info.major > 2:
    pytest.skip(msg="not yet ported to python3", allow_module_level=True)
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
