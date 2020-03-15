"""Unit test module for access URLs"""

from flask import url_for
from flask_webtest import SessionScope
import pytest

from portal.extensions import db, user_manager
from portal.models.organization import Organization
from portal.models.role import ROLE


@pytest.fixture
def write_only_user(add_user, promote_user):
    write_only = add_user('one@time.com', first_name='first', last_name='last')
    promote_user(user=write_only, role_name=ROLE.WRITE_ONLY.value)
    return write_only


@pytest.fixture
def admin_user(write_only_user, promote_user):
    promote_user(user=write_only_user, role_name=ROLE.ADMIN.value)
    return write_only_user


def test_create_access_url(
        app, client, admin_user, login, teardown_db):
    login()
    onetime = db.session.merge(admin_user)
    response = client.get('/api/user/{}/access_url'.format(
        onetime.id))
    assert response.status_code == 200

    # confirm we obtained a valid token
    access_url = response.json['access_url']
    token = access_url.split('/')[-1]
    is_valid, has_expired, id = user_manager.token_manager.verify_token(
        token, 10)
    assert is_valid
    assert not has_expired
    assert id == onetime.id


def test_use_access_url(
        client, write_only_user, assert_redirects, teardown_db):
    """The current flow forces access to the challenge page"""
    onetime = db.session.merge(write_only_user)
    onetime.birthdate = '01-31-1969'  # verify requires DOB

    token = user_manager.token_manager.generate_token(onetime.id)
    access_url = url_for(
        'portal.access_via_token', token=token, _external=True)

    response = client.get(access_url)
    assert_redirects(
        response,
        url_for('portal.challenge_identity', request_path=access_url))


def test_bad_token(client):
    token = 'TBKSYw7iHndUT3DfaED9tw.DHZMrQ.Wwr8SPM7ylABWf0mQHhGHHwttYk'
    access_url = url_for('portal.access_via_token', token=token)

    response = client.get(access_url)
    assert response.status_code == 404
