"""Test identifiers"""

import json

from flask_webtest import SessionScope
import pytest
from werkzeug.exceptions import Conflict

from portal.extensions import db
from portal.models.identifier import Identifier
from portal.models.user import User
from tests import TEST_USER_ID


def testGET(test_user, login, client):
    test_user = db.session.merge(test_user)
    expected = len(test_user.identifiers)
    login()
    response = client.get('/api/user/{}/identifier'.format(TEST_USER_ID))
    assert response.status_code == 200
    assert len(response.json['identifier']) == expected


def testPOST(test_user, login, client):
    test_user = db.session.merge(test_user)
    """Add an existing and fresh identifier - confirm it sticks"""
    expected = len(test_user.identifiers) + 2
    existing = Identifier(system='http://notreal.com', value='unique')
    with SessionScope(db):
        db.session.add(existing)
        db.session.commit()
    existing = db.session.merge(existing)
    fresh = Identifier(system='http://another.com', value='unique')
    data = {'identifier': [i.as_fhir() for i in (existing, fresh)]}
    login()
    response = client.post(
        '/api/user/{}/identifier'.format(TEST_USER_ID),
        content_type='application/json', data=json.dumps(data))
    assert response.status_code == 200
    assert len(response.json['identifier']) == expected
    user = User.query.get(TEST_USER_ID)
    assert len(user.identifiers) == expected

    # Insert the same, expect idempotent reaction
    response = client.post(
        '/api/user/{}/identifier'.format(TEST_USER_ID),
        content_type='application/json', data=json.dumps(data))
    assert response.status_code == 200
    assert len(response.json['identifier']) == expected
    user = User.query.get(TEST_USER_ID)
    assert len(user.identifiers) == expected


def test_unique(add_user, test_user):
    """Try adding a non-unique identifier, expect exception"""
    constrained = Identifier(
        system='http://us.truenth.org/identity-codes/external-study-id',
        value='unique-one')
    with SessionScope(db):
        db.session.add(constrained)
    second_user = add_user('second')
    constrained = db.session.merge(constrained)
    second_user.add_identifier(constrained)

    user = db.session.merge(test_user)
    with pytest.raises(Conflict):
        user.add_identifier(constrained)


def test_unique_api(add_user, login, client, test_user):
    constrained = Identifier(
        system='http://us.truenth.org/identity-codes/external-study-id',
        value='unique-one')
    with SessionScope(db):
        db.session.add(constrained)
    second_user = add_user('second')
    constrained = db.session.merge(constrained)
    second_user.add_identifier(constrained)

    login()
    response = client.get(
        '/api/user/{}/unique'.format(TEST_USER_ID),
        query_string={'identifier': '|'.join((
            constrained.system, constrained.value))})
    assert response.status_code == 200
    assert response.json['unique'] is False


def test_unique_deleted(add_user, test_user):
    """Try adding a non-unique identifier from deleted user"""
    constrained = Identifier(
        system='http://us.truenth.org/identity-codes/external-study-id',
        value='unique-one')
    with SessionScope(db):
        db.session.add(constrained)
    second_user = add_user('second')
    constrained = db.session.merge(constrained)
    second_user.add_identifier(constrained)
    test_user = db.session.merge(test_user)
    second_user.delete_user(acting_user=test_user)

    user = db.session.merge(test_user)
    user.add_identifier(constrained)
    assert constrained in user.identifiers


def test_unicode_value():
    ex = Identifier(system='http://nonsense.com', value='ascii')
    unicode_string = '__invite__justin.emcee\xb1jm050417C@gmail.com'
    ex.value = unicode_string
    assert ex.value == unicode_string
