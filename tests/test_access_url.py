"""Unit test module for access URLs"""
from flask import url_for
from flask_webtest import SessionScope

from portal.extensions import db, user_manager
from portal.models.role import ROLE
from tests import TestCase, TEST_USER_ID


class TestAccessUrl(TestCase):

    def test_create_access_url(self):
        onetime = self.add_user('one@time.com')
        self.promote_user(user=onetime, role_name=ROLE.WRITE_ONLY)

        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        onetime = db.session.merge(onetime)
        rv = self.app.get('/api/user/{}/access_url'.format(onetime.id))
        self.assert200(rv)

        # confirm we obtained a valid token
        access_url = rv.json['access_url']
        token = access_url.split('/')[-1]
        is_valid, has_expired, id =\
                user_manager.token_manager.verify_token(token, 10)
        self.assertTrue(is_valid)
        self.assertFalse(has_expired)
        self.assertEquals(id, onetime.id)

    def test_use_access_url(self):
        onetime = self.add_user('one@time.com')
        self.promote_user(user=onetime, role_name=ROLE.WRITE_ONLY)
        onetime = db.session.merge(onetime)

        token = user_manager.token_manager.generate_token(onetime.id)
        access_url = url_for('portal.access_via_token', token=token)

        rv = self.app.get(access_url)

        # Hack - workaround for test_client being monkeypatched to self.app
        # See https://github.com/uwcirg/true_nth_usa_portal/blob/develop/tests/__init__.py#L204
        self.app.config = self.app.application.config

        # User should be redirected to confirm identity
        self.assert_redirects(rv, url_for('portal.challenge_identity'))
