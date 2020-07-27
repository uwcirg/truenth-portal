import json

from flask import url_for
from flask_webtest import SessionScope
import pytest

from portal.database import db
from portal.extensions import user_manager


@pytest.fixture
def access_on_verify_user(add_user, promote_user):
    weak_access_user = add_user(username='fake@org.com')
    promote_user(weak_access_user, role_name='access_on_verify')
    return db.session.merge(weak_access_user)


def test_create_account_via_api(app, client, service_user, login):
    # use APIs to create account w/ special role
    db.session.add(service_user)
    login(user_id=service_user.id)
    response = client.post(
        '/api/account',
        json={})
    assert response.status_code == 200

    # add role to account
    user_id = response.json['user_id']
    data = {'roles': [{'name': 'access_on_verify'}]}
    response = client.put(
        '/api/user/{user_id}/roles'.format(user_id=user_id),
        json=data)
    assert response.status_code == 200


def test_access(client, access_on_verify_user, assert_redirects):
    # confirm exception on access w/o DOB
    assert not access_on_verify_user.birthdate

    token = user_manager.token_manager.generate_token(access_on_verify_user.id)
    access_url = url_for(
        'portal.access_via_token', token=token, _external=True)

    response = client.get(access_url)
    assert response.status_code == 400

    # add DOB & names and expect redirect to challenge
    access_on_verify_user.birthdate = '01-31-1999'
    access_on_verify_user.first_name = 'Testy'
    access_on_verify_user.last_name = 'User'
    with SessionScope(db):
        db.session.commit()

    response = client.get(access_url)
    assert_redirects(
        response,
        url_for('portal.challenge_identity', request_path=access_url))
