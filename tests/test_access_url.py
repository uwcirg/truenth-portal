"""Unit test module for access URLs"""
from datetime import datetime
from flask import url_for
from flask_webtest import SessionScope

from portal.extensions import db, user_manager
from portal.models.role import ROLE
from portal.models.user_document import UserDocument
from tests import TestCase


class TestAccessUrl(TestCase):

    def test_create_access_url(self):
        onetime = self.add_user('one@time.com')
        self.promote_user(user=onetime, role_name=ROLE.WRITE_ONLY)

        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        onetime = db.session.merge(onetime)
        rv = self.client.get('/api/user/{}/access_url'.format(onetime.id))
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
        """The current flow forces access to the challenge page"""
        onetime = self.add_user(
            'one@time.com', first_name='first', last_name='last')
        onetime.birthdate = '01-31-1969'  # verify requires DOB
        self.promote_user(user=onetime, role_name=ROLE.WRITE_ONLY)
        onetime = db.session.merge(onetime)

        token = user_manager.token_manager.generate_token(onetime.id)
        access_url = url_for('portal.access_via_token', token=token)

        rv = self.client.get(access_url)
        self.assert_redirects(rv, url_for('portal.challenge_identity'))

    def test_bad_token(self):
        token = 'TBKSYw7iHndUT3DfaED9tw.DHZMrQ.Wwr8SPM7ylABWf0mQHhGHHwttYk'
        access_url = url_for('portal.access_via_token', token=token)

        rv = self.client.get(access_url)
        self.assert404(rv)

    def test_verify_access_url(self):
        """The current flow forces access to the challenge page"""
        onetime = self.add_user(
            'one@time.com', first_name='first', last_name='last')
        onetime.birthdate = '01-31-1969'  # verify requires DOB
        self.promote_user(user=onetime, role_name=ROLE.ACCESS_ON_VERIFY)
        onetime = db.session.merge(onetime)

        token = user_manager.token_manager.generate_token(onetime.id)
        access_url = url_for('portal.access_via_token', token=token)

        rv = self.client.get(access_url)
        self.assert_redirects(rv, url_for('portal.challenge_identity'))

    def test_verify_access_url_with_doc(self):
        """access_on_verify plus user doc sends to register post challenge"""
        onetime = self.add_user(
            'one@time.com', first_name='first', last_name='last')
        onetime.birthdate = '01-31-1969'  # verify requires DOB
        self.promote_user(user=onetime, role_name=ROLE.ACCESS_ON_VERIFY)
        onetime = db.session.merge(onetime)
        ud = UserDocument(
            user_id=onetime.id,
            document_type="TestFile", uploaded_at=datetime.utcnow(),
            filename="test_file_1.txt", filetype="txt", uuid="012345")
        onetime.documents.append(ud)
        with SessionScope(db):
            db.session.add(ud)
            db.session.commit()
        onetime = db.session.merge(onetime)

        token = user_manager.token_manager.generate_token(onetime.id)
        access_url = url_for('portal.access_via_token', token=token)

        rv = self.client.get(access_url)
        self.assert_redirects(rv, url_for('portal.challenge_identity'))
