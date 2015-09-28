"""Unit test module for auth"""
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.auth import Client

class TestAuth(TestCase):
    """Auth API tests"""

    def test_nouser_logout(self):
        """Confirm logout works without a valid user"""
        rv = self.app.get('/logout')

    def test_client_edit(self):
        """Test editing a client application"""
        # Generate a minimal client belonging to test user
        client_id = 'test_client'
        client = Client(client_id=client_id,
                client_secret='tc_secret', user_id=TEST_USER_ID)
        db.session.add(client)
        db.session.commit()
        self.promote_user(role_name='application_developer')
        self.login()
        rv = self.app.post('/client/{0}'.format(client.client_id),
                data=dict(callback_url='http://tryme.com'))

        client = Client.query.get('test_client')
        self.assertEquals(client.callback_url, 'http://tryme.com')
