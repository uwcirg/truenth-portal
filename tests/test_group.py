"""Unit test module for group model"""

import json

from flask_webtest import SessionScope
import pytest
from werkzeug.exceptions import BadRequest

from portal.extensions import db
from portal.models.group import Group
from portal.models.role import ROLE
from tests import TEST_USER_ID, TestCase


class TestGroup(TestCase):
    """Group model tests"""

    def test_from_json(self):
        data = {'name': 'random_group_name',
                'description': 'with a windy description'}
        grp = Group.from_json(data)
        assert grp.name == data['name']
        assert grp.description == data['description']

    def test_invalid_name(self):
        data = {'name': 'name with a space',
                'description': 'with a windy description'}
        with pytest.raises(BadRequest):
            Group.from_json(data)

    def test_group_get(self):
        grp = Group(name='test')
        with SessionScope(db):
            db.session.add(grp)
            db.session.commit()
        grp = db.session.merge(grp)

        # use api to obtain
        self.login()
        response = self.client.get('/api/group/{}'.format(grp.name))
        assert response.status_code == 200
        assert response.json['group']['name'] == 'test'

    def test_group_list(self):
        grp1 = Group(name='test_1')
        grp2 = Group(name='test_2')
        with SessionScope(db):
            db.session.add(grp1)
            db.session.add(grp2)
            db.session.commit()

        # use api to obtain list
        self.login()
        response = self.client.get('/api/group/')
        assert response.status_code == 200
        bundle = response.json
        assert len(bundle['groups']) == 2

    def test_group_post(self):
        grp = Group(name='test', description='test group')

        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()
        response = self.client.post(
            '/api/group/', content_type='application/json',
            data=json.dumps(grp.as_json()))
        assert response.status_code == 200

        # Pull the posted group
        grp2 = Group.query.filter_by(name='test').one()
        assert grp2.name == grp.name
        assert grp2.description == grp.description

    def test_group_edit(self):
        grp = Group(name='test_grp_name', description='test group')
        with SessionScope(db):
            db.session.add(grp)
            db.session.commit()

        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()

        improved_grp = Group(name='changed_name', description='Updated')
        response = self.client.put(
            '/api/group/{}'.format('test_grp_name'),
            content_type='application/json',
            data=json.dumps(improved_grp.as_json()))
        assert response.status_code == 200

        # Pull the posted group
        grp2 = Group.query.one()
        assert grp2.name == improved_grp.name
        assert grp2.description == improved_grp.description

    def test_user_no_groups(self):
        self.login()
        response = self.client.get('/api/user/{}/groups'.format(TEST_USER_ID))
        assert response.status_code == 200
        assert len(response.json['groups']) == 0

    def test_user_groups(self):
        grp1 = Group(name='test_1')
        grp2 = Group(name='test_2')
        self.test_user.groups.append(grp1)
        self.test_user.groups.append(grp2)
        with SessionScope(db):
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        self.login()
        response = self.client.get('/api/user/{}/groups'.format(TEST_USER_ID))
        assert response.status_code == 200
        assert len(response.json['groups']) == 2

    def test_put_user_groups(self):
        grp1 = Group(name='test1')
        grp2 = Group(name='test2')
        self.test_user.groups.append(grp1)
        with SessionScope(db):
            db.session.add(grp2)
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)

        # initially grp 1 is the only for the user
        assert self.test_user.groups[0].name == 'test1'
        grp2 = db.session.merge(grp2)

        # put only the 2nd group, should end up being the only one for the user
        self.login()
        response = self.client.put(
            '/api/user/{}/groups'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps({'groups': [grp2.as_json()]}))
        assert response.status_code == 200
        assert len(self.test_user.groups) == 1
        assert self.test_user.groups[0].name == 'test2'
