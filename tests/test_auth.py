"""Unit test module for auth"""
from __future__ import unicode_literals  # isort:skip
from collections import namedtuple
import datetime

from flask import url_for
from flask_webtest import SessionScope
import pytest
from werkzeug.exceptions import Unauthorized

from portal.extensions import db
from portal.models.auth import (
    AuthProvider,
    Token,
    create_service_token,
)
from portal.models.client import Client, validate_origin
from portal.models.intervention import INTERVENTION
from portal.models.role import ROLE
from portal.models.user import (
    LOCKOUT_PERIOD,
    PERMITTED_FAILED_LOGIN_ATTEMPTS,
    RoleError,
    User,
    UserRelationship,
    add_role,
    add_user,
)
from tests import (
    OAUTH_INFO_PROVIDER_LOGIN,
    TEST_USER_ID,
    TestCase,
)


class TestAuth(TestCase):
    """Auth API tests"""

    def test_require_tld(self):
        """we need the require_tld arg in validators.url for localhost"""
        import validators
        assert validators.url('http://localhost', require_tld=False)

    def test_nouser_logout(self):
        """Confirm logout works without a valid user"""
        response = self.client.get('/logout')
        assert 302 == response.status_code

    def test_local_user_add(self):
        """Add a local user via flask_user forms"""
        data = {
            'password': 'one2Three',
            'retype_password': 'one2Three',
            'email': 'otu@example.com'}
        response = self.client.post('/user/register', data=data)
        assert response.status_code == 302
        new_user = User.query.filter_by(username=data['email']).first()
        assert new_user.active is True

    def test_local_login_valid_username_and_password(self):
        """login through the login form"""
        # Create a user
        email = 'localuser@test.com'
        password = 'Password1'
        user = self.add_user(
            username='username',
            email=email,
            password=password
        )

        # Attempt to login with valid creds
        response = self.local_login(user.email, password)

        # Validate login was successful
        assert response.status_code is 200
        assert user.password_verification_failures == 0

    def test_local_login_failure_increments_lockout(self):
        """login through the login form"""
        # Create a user
        email = 'localuser@test.com'
        password = 'Password1'
        user = self.add_user(
            username='username',
            email=email,
            password=password
        )

        # Attempt to login with an invalid password
        response = self.local_login(user.email, 'invalidpassword')

        # Verify there was a password failure
        db.session.refresh(user)
        assert user.password_verification_failures == 1

    def test_local_login_valid_username_and_password_resets_lockout(self):
        """login through the login form"""
        # Create a user
        email = 'localuser@test.com'
        password = 'Password1'
        user = self.add_user(
            username='username',
            email=email,
            password=password
        )

        # Mock a failed password attempt
        user.add_password_verification_failure()
        assert user.password_verification_failures == 1

        # Atempt to login with valid creds
        response = self.local_login(user.email, password)

        # Verify lockout was reset
        db.session.refresh(user)
        assert user.password_verification_failures == 0

    def test_local_login_lockout_after_unsuccessful_attempts(self):
        """login through the login form"""
        email = 'localuser@test.com'
        password = 'Password1'
        user = self.add_user(
            username='username',
            email=email,
            password=password
        )

        # Use up all of the permitted login attempts
        for failureIndex in range(0, PERMITTED_FAILED_LOGIN_ATTEMPTS):
            response = self.local_login(user.email, 'invalidpassword')
            assert response.status_code is 200

            db.session.refresh(user)
            assert user.password_verification_failures == (failureIndex + 1)
            assert not user.is_locked_out

        # Validate that after using up all permitted attempts
        # the next is locked out
        response = self.local_login(user.email, 'invalidpassword')
        db.session.refresh(user)
        assert user.is_locked_out

    def test_local_login_verify_lockout_resets_after_lockout_period(self):
        """login through the login form"""
        email = 'localuser@test.com'
        password = 'Password1'
        user = self.add_user(
            username='username',
            email=email,
            password=password
        )

        # Lock the user out
        for failureIndex in range(0, PERMITTED_FAILED_LOGIN_ATTEMPTS + 1):
            user.add_password_verification_failure()

        # Verify the user is locked out
        assert user.is_locked_out

        # Move time to the end of the lockout period
        user.last_password_verification_failure = \
            datetime.datetime.utcnow() - LOCKOUT_PERIOD

        # Verify we are no longer locked out
        assert not user.is_locked_out

    def test_local_login_verify_cant_login_when_locked_out(self):
        """login through the login form"""
        email = 'localuser@test.com'
        password = 'Password1'
        user = self.add_user(
            username='username',
            email=email,
            password=password
        )

        # Lock the user out
        for failureIndex in range(0, PERMITTED_FAILED_LOGIN_ATTEMPTS + 1):
            user.add_password_verification_failure()

        assert user.is_locked_out

        # Atempt to login with valid creds
        response = self.local_login(user.email, password)

        # Verify the user is still locked out
        assert user.is_locked_out

    def test_register_now(self):
        """Initiate process to register exiting account"""
        self.app.config['NO_CHALLENGE_WO_DATA'] = False
        self.test_user.password = None
        self.test_user.birthdate = '1998-01-31'
        self.promote_user(role_name=ROLE.ACCESS_ON_VERIFY.value)
        user = db.session.merge(self.test_user)
        email = user.email
        self.login()

        response = self.client.get('/api/user/register-now')
        self.assertRedirects(response, url_for('user.register', email=email))

    def test_client_add(self):
        """Test adding a client application"""
        origins = "https://test.com https://two.com"
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER.value)
        self.login()
        response = self.client.post('/client', data=dict(
            application_origins=origins))
        assert 302 == response.status_code

        client = Client.query.filter_by(user_id=TEST_USER_ID).first()
        assert client.application_origins == origins

    def test_client_bad_add(self):
        """Test adding a bad client application"""
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER.value)
        self.login()
        response = self.client.post(
            '/client',
            data=dict(application_origins="bad data in")).get_data(
            as_text=True)
        assert "Invalid URL" in response

    def test_client_edit(self):
        """Test editing a client application"""
        client = self.add_client()
        test_url = 'http://tryme.com'
        origins = "{} {}".format(client.application_origins, test_url)
        self.login()
        response = self.client.post(
            '/client/{0}'.format(client.client_id),
            data=dict(
                callback_url=test_url, application_origins=origins,
                application_role=INTERVENTION.DEFAULT.name))
        assert 302 == response.status_code

        client = Client.query.get('test_client')
        assert client.callback_url == test_url

        invalid_url = "http://invalid.org"
        response2 = self.client.post(
            '/client/{0}'.format(client.client_id),
            data=dict(
                callback_url=invalid_url, application_origins=origins,
                application_role=INTERVENTION.DEFAULT.name))
        # 200 response, because page is reloaded with validation errors
        assert 200 == response2.status_code
        error_text = 'URL host must match a provided Application Origin URL'
        assert error_text in response2.get_data(as_text=True)

        client = Client.query.get('test_client')
        assert client.callback_url != invalid_url

    def test_callback_validation(self):
        """Confirm only valid urls can be set"""
        client = self.add_client()
        self.login()
        response = self.client.post(
            '/client/{0}'.format(client.client_id),
            data=dict(
                callback_url='badprotocol.com',
                application_origins=client.application_origins))
        assert 200 == response.status_code

        client = Client.query.get('test_client')
        assert client.callback_url is None

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
        assert len(service_user.roles) == 1
        assert 'service' == service_user.roles[0].name
        sponsorship = UserRelationship.query.filter_by(
            other_user_id=service_user.id).first()
        assert sponsorship.user_id == TEST_USER_ID
        assert sponsorship.relationship.name == 'sponsor'

        # Can we get a usable Bearer Token
        create_service_token(client=client, user=service_user)
        token = Token.query.filter_by(user_id=service_user.id).first()
        assert token

        # The token should have a very long life
        assert (token.expires > datetime.datetime.utcnow()
                + datetime.timedelta(days=364))

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
        assert pytest.raises(RoleError, add_role, service_user,
                             ROLE.APPLICATION_DEVELOPER.value)

        assert len(service_user.roles) == 1

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
        response = self.client.get(
            "/oauth/token-status",
            headers={'Authorization': 'Bearer {}'.format(token.access_token)})
        assert 200 == response.status_code
        data = response.json
        assert pytest.approx(30, 5) == data['expires_in']

    def test_token_status_wo_header(self):
        """Call for token_status w/o token should return 401"""
        response = self.client.get("/oauth/token-status")
        assert 401 == response.status_code

    def test_origin_validation(self):
        client = self.add_client()
        client_url = client._redirect_uris
        local_url = "http://{}/home?test".format(
            self.app.config.get('SERVER_NAME'))
        invalid_url = 'http://invalid.org'

        assert validate_origin(client_url)
        assert validate_origin(local_url)
        assert pytest.raises(Unauthorized, validate_origin, invalid_url)

    def test_oauth_with_new_auth_provider_and_new_user(self):
        # Login using the test backdoor
        response = self.login(oauth_info=OAUTH_INFO_PROVIDER_LOGIN)

        # Verify a new user was created
        user = User.query.filter_by(
            email=OAUTH_INFO_PROVIDER_LOGIN['email']
        ).first()
        assert user

        # Verify a new auth provider was created
        assert AuthProvider.query.filter_by(
            provider=OAUTH_INFO_PROVIDER_LOGIN['provider_name'],
            provider_id=OAUTH_INFO_PROVIDER_LOGIN['provider_id'],
            user_id=user.id,
        ).first()

    def test_oauth_with_new_auth_provider_and_new_user_unicode_name(self):
        # Set a unicode name
        oauth_info = dict(OAUTH_INFO_PROVIDER_LOGIN)
        oauth_info['last_name'] = 'Bugn\xed'

        # Login using the test backdoor
        response = self.login(oauth_info=OAUTH_INFO_PROVIDER_LOGIN)

        # Verify a new user was created
        user = User.query.filter_by(
            last_name=OAUTH_INFO_PROVIDER_LOGIN['last_name']
        ).first()
        assert user

        # Verify a new auth provider was created
        assert AuthProvider.query.filter_by(
            provider=OAUTH_INFO_PROVIDER_LOGIN['provider_name'],
            provider_id=OAUTH_INFO_PROVIDER_LOGIN['provider_id'],
            user_id=user.id,
        ).first()

        pass

    def test_oauth_with_new_auth_provider_and_existing_user(self):
        # Create the user
        user = add_user_from_oauth_info(OAUTH_INFO_PROVIDER_LOGIN)

        # Login through the test backdoor
        response = self.login(oauth_info=OAUTH_INFO_PROVIDER_LOGIN)

        # Verify the response returned successfully
        assert response.status_code == 200

        # Verify a new auth provider was created
        assert AuthProvider.query.filter_by(
            provider=OAUTH_INFO_PROVIDER_LOGIN['provider_name'],
            provider_id=OAUTH_INFO_PROVIDER_LOGIN['provider_id'],
            user_id=user.id,
        ).first()

    def test_oauth_with_existing_auth_provider_and_existing_user(self):
        # Create the user
        user = add_user_from_oauth_info(OAUTH_INFO_PROVIDER_LOGIN)

        # Create the auth provider
        add_auth_provider(OAUTH_INFO_PROVIDER_LOGIN, user)

        # Login through the test backdoor
        response = self.login(oauth_info=OAUTH_INFO_PROVIDER_LOGIN)

        # Verify the response returned successfully
        assert response.status_code == 200

    def test_oauth_when_mock_provider_fails_to_get_user_json(self):
        # Make the mock provider fail to get user json
        oauth_info = dict(OAUTH_INFO_PROVIDER_LOGIN)
        oauth_info['fail_to_get_user_json'] = True

        # Attempt to login through the test backdoor
        response = self.login(oauth_info=oauth_info)

        # Verify 500
        assert response.status_code == 500

    def test_oauth_when_non_required_value_undefined(self):
        # Make the mock provider fail to get user json
        oauth_info = dict(OAUTH_INFO_PROVIDER_LOGIN)
        del oauth_info['birthdate']

        # Attempt to login through the test backdoor
        response = self.login(oauth_info=oauth_info)

        # Verify the response returned successfully
        assert response.status_code == 200

    def test_oauth_when_required_value_undefined(self):
        # Make the mock provider fail to get user json
        oauth_info = dict(OAUTH_INFO_PROVIDER_LOGIN)
        del oauth_info['provider_id']

        # Attempt to login through the test backdoor
        response = self.login(oauth_info=oauth_info)

        # Verify 500
        assert response.status_code == 500

    def test_oauth_with_invalid_token(self):
        # Set an invalid token
        oauth_info = dict(OAUTH_INFO_PROVIDER_LOGIN)
        oauth_info.pop('token', None)

        # Attempt to login through the test backdoor
        response = self.login(oauth_info=oauth_info, follow_redirects=False)

        # Verify force reload
        self.assertRedirects(response, oauth_info['next'])


def add_user_from_oauth_info(oauth_info):
    user_to_add = namedtuple('Mock', oauth_info.keys())(*oauth_info.values())
    user = add_user(user_to_add)
    db.session.commit()
    return user


def add_auth_provider(oauth_info, user):
    auth_provider = AuthProvider(
        provider=oauth_info['provider_name'],
        provider_id=oauth_info['provider_id'],
        user=user,
    )
    db.session.add(auth_provider)
    db.session.commit()
    return auth_provider
