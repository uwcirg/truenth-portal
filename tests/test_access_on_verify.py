
import json

from flask import url_for
from flask_webtest import SessionScope

from portal.database import db
from portal.extensions import user_manager
from tests import TestCase


class TestAccessOnVerify(TestCase):

    def test_create_account_via_api(self):
        # use APIs to create account w/ special role
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)
        response = self.client.post(
            '/api/account',
            data=json.dumps({}),
            content_type='application/json')
        assert response.status_code == 200

        # add role to account
        user_id = response.json['user_id']
        data = {'roles': [{'name': 'access_on_verify'}]}
        response = self.client.put(
            '/api/user/{user_id}/roles'.format(user_id=user_id),
            data=json.dumps(data),
            content_type='application/json')
        assert response.status_code == 200

    def test_access(self):
        # confirm exception on access w/o DOB
        weak_access_user = self.add_user(username='fake@org.com')
        self.promote_user(weak_access_user, role_name='access_on_verify')
        weak_access_user = db.session.merge(weak_access_user)
        assert not weak_access_user.birthdate

        token = user_manager.token_manager.generate_token(weak_access_user.id)
        access_url = url_for(
            'portal.access_via_token', token=token, _external=True)

        response = self.client.get(access_url)
        assert response.status_code == 400

        # add DOB & names and expect redirect to challenge
        weak_access_user.birthdate = '01-31-1999'
        weak_access_user.first_name = 'Testy'
        weak_access_user.last_name = 'User'
        with SessionScope(db):
            db.session.commit()

        response = self.client.get(access_url)
        self.assert_redirects(
            response,
            url_for('portal.challenge_identity', request_path=access_url))
