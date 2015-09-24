"""Unit test module for auth"""
import json
from flask.ext.login import login_user, logout_user
from tests import TestCase, LAST_NAME, FIRST_NAME, TEST_USER_ID

from portal.extensions import db
from portal.models.auth import Client

class TestAuth(TestCase):

    def test_client_edit(self):
        # Generate a minimal client belonging to test user
        client_id = 'test_client'
        client = Client(client_id=client_id,
                client_secret='tc_secret', user_id=TEST_USER_ID)
        db.session.add(client)
        db.session.commit()
        self.login()
        rv = self.app.post('/client/{0}'.format(client.client_id),
                data=dict(callback_url='http://tryme.com'))

        self.assertEquals(rv.status_code, 200)
        client = Client.query.get('test_client')
        self.assertEquals(client.callback_url, 'http://tryme.com')
