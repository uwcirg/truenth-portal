"""Unit test module for auth"""
import datetime
from tests import TestCase, TEST_USER_ID
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.auth import Client, Token, create_service_token
from portal.models.intervention import INTERVENTION
from portal.models.role import ROLE
from portal.models.user import add_authomatic_user, add_role
from portal.models.user import RoleError, User, UserRelationship

class AuthomaticMock(object):
    """Simple container for mocking Authomatic response"""
    pass


class TestAuth(TestCase):
    """Auth API tests"""

    def test_require_tld(self):
        """we need the require_tld arg in validators.url for localhost"""
        import validators
        self.assertTrue(validators.url('http://localhost', require_tld=False))

    def test_nouser_logout(self):
        """Confirm logout works without a valid user"""
        rv = self.client.get('/logout')
        self.assertEquals(302, rv.status_code)

    def test_local_user_add(self):
        """Add a local user via flask_user forms"""
        data = {
                'password': 'one2Three',
                'retype_password': 'one2Three',
                'email': 'otu@example.com',
               }
        rv = self.client.post('/user/register', data=data)
        self.assertEquals(rv.status_code, 302)
        new_user = User.query.filter_by(username=data['email']).first()
        self.assertEquals(new_user.active, True)

    def test_client_add(self):
        """Test adding a client application"""
        origins = "https://test.com https://two.com"
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER)
        self.login()
        rv = self.client.post('/client', data=dict(
            application_origins=origins))
        self.assertEquals(302, rv.status_code)

        client = Client.query.filter_by(user_id=TEST_USER_ID).first()
        self.assertEquals(client.application_origins, origins)

    def test_client_bad_add(self):
        """Test adding a bad client application"""
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER)
        self.login()
        rv = self.client.post('/client',
                data=dict(application_origins="bad data in"))
        self.assertTrue("Invalid URL" in rv.data)

    def test_client_edit(self):
        """Test editing a client application"""
        client = self.add_client()
        self.login()
        rv = self.client.post('/client/{0}'.format(client.client_id),
                data=dict(callback_url='http://tryme.com',
                         application_origins=client.application_origins,
                         application_role=INTERVENTION.DEFAULT.name))
        self.assertEquals(302, rv.status_code)

        client = Client.query.get('test_client')
        self.assertEquals(client.callback_url, 'http://tryme.com')

    def test_unicode_name(self):
        """Test insertion of unicode name via add_authomatic_user"""
        # Bug with unicode characters in a google user's name
        # mock an authomatic class:

        authomatic_user = AuthomaticMock()
        authomatic_user.name = 'Test User'
        authomatic_user.first_name = 'Test'
        authomatic_user.last_name = u'Bugn\xed'
        authomatic_user.birth_date = None
        authomatic_user.gender = u'male'
        authomatic_user.email = 'test@test.org'

        new_user = add_authomatic_user(authomatic_user, None)

        user = User.query.filter_by(email='test@test.org').first()
        self.assertEquals(user.last_name, u'Bugn\xed')
        self.assertEquals(new_user, user)

    def test_callback_validation(self):
        """Confirm only valid urls can be set"""
        client = self.add_client()
        self.login()
        rv = self.client.post('/client/{0}'.format(client.client_id),
                data=dict(callback_url='badprotocol.com',
                    application_origins=client.application_origins))
        self.assertEquals(200, rv.status_code)

        client = Client.query.get('test_client')
        self.assertEquals(client.callback_url, None)

    def test_service_account_creation(self):
        """Confirm we can create a service account and token"""
        client = self.add_client()
        test_user = User.query.get(TEST_USER_ID)
        service_user = test_user.add_service_account()

        with SessionScope(db):
            db.session.add(service_user)
            db.session.add(client)
            db.session.commit()
        service_user = db.session.merge(service_user)
        client = db.session.merge(client)

        # Did we get a service account with the correct roles and relationships
        self.assertEquals(len(service_user.roles), 1)
        self.assertEquals('service', service_user.roles[0].name)
        sponsorship = UserRelationship.query.filter_by(
            other_user_id=service_user.id).first()
        self.assertEquals(sponsorship.user_id, TEST_USER_ID)
        self.assertEquals(sponsorship.relationship.name, 'sponsor')

        # Can we get a usable Bearer Token
        create_service_token(client=client, user=service_user)
        token = Token.query.filter_by(user_id=service_user.id).first()
        self.assertTrue(token)

        # The token should have a very long life
        self.assertTrue(token.expires > datetime.datetime.utcnow() +
                        datetime.timedelta(days=364))


    def test_service_account_promotion(self):
        """Confirm we can not promote a service account """
        self.add_client()
        test_user = User.query.get(TEST_USER_ID)
        service_user = test_user.add_service_account()

        with SessionScope(db):
            db.session.add(service_user)
            db.session.commit()
        service_user = db.session.merge(service_user)

        # try to promote - which should fail
        self.assertRaises(RoleError, add_role, service_user,
                          ROLE.APPLICATION_DEVELOPER)
        self.assertEquals(len(service_user.roles), 1)

    def test_token_status(self):
        with SessionScope(db):
            client = Client(
                client_id='test-id', client_secret='test-secret',
                user_id=TEST_USER_ID)
            token = Token(
                access_token='test-token', client=client, user_id=TEST_USER_ID,
                token_type='bearer',
                expires=(datetime.datetime.utcnow() +
                         datetime.timedelta(seconds=30)))
            db.session.add(client)
            db.session.add(token)
            db.session.commit()

        token = db.session.merge(token)
        rv = self.client.get(
            "/oauth/token-status",
            headers={'Authorization': 'Bearer {}'.format(token.access_token)})
        self.assert200(rv)
        data = rv.json
        self.assertAlmostEquals(30, data['expires_in'], delta=5)

    def test_token_status_wo_header(self):
        """Call for token_status w/o token should return 401"""
        rv = self.client.get("/oauth/token-status")
        self.assert401(rv)
