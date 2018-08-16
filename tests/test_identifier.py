"""Test identifiers"""
from __future__ import unicode_literals  # isort:skip

import json

from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.identifier import Identifier
from portal.models.user import User
from tests import TEST_USER_ID, TestCase


class TestIdentifier(TestCase):

    def testGET(self):
        expected = len(self.test_user.identifiers)
        self.login()
        response = self.client.get('/api/user/{}/identifier'
                                   .format(TEST_USER_ID))
        assert response.status_code == 200
        assert len(response.json['identifier']) == expected

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
        response = self.client.post(
            '/api/user/{}/identifier'.format(TEST_USER_ID),
            content_type='application/json', data=json.dumps(data))
        assert response.status_code == 200
        assert len(response.json['identifier']) == expected
        user = User.query.get(TEST_USER_ID)
        assert len(user.identifiers) == expected
