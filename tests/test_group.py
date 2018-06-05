"""Unit test module for group model"""
from flask_webtest import SessionScope
from werkzeug.exceptions import BadRequest
import json

from portal.extensions import db
from portal.models.group import Group
from portal.models.role import ROLE
from tests import TestCase, TEST_USER_ID


class TestGroup(TestCase):
    """Group model tests"""

    def test_from_json(self):
        data = {'name': 'random_group_name',
                'description': 'with a windy description'}
        grp = Group.from_json(data)
        self.assertEqual(grp.name,
                          data['name'])
        self.assertEqual(grp.description,
                          data['description'])

    def test_invalid_name(self):
        data = {'name': 'name with a space',
                'description': 'with a windy description'}
        self.assertRaises(BadRequest, Group.from_json, data)

    def test_group_get(self):
        grp = Group(name='test')
        with SessionScope(db):
            db.session.add(grp)
            db.session.commit()
        grp = db.session.merge(grp)

        # use api to obtain
        self.login()
        rv = self.client.get('/api/group/{}'.format(grp.name))
        self.assert200(rv)
        self.assertEqual(rv.json['group']['name'], 'test')

    def test_group_list(self):
        grp1 = Group(name='test_1')
        grp2 = Group(name='test_2')
        with SessionScope(db):
            db.session.add(grp1)
            db.session.add(grp2)
            db.session.commit()

        # use api to obtain list
        self.login()
        rv = self.client.get('/api/group/')
        self.assert200(rv)
        bundle = rv.json
        self.assertEqual(len(bundle['groups']), 2)

    def test_group_post(self):
        grp = Group(name='test', description='test group')

        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.client.post('/api/group/',
                          content_type='application/json',
                          data=json.dumps(grp.as_json()))
        self.assert200(rv)

        # Pull the posted group
        grp2 = Group.query.filter_by(name='test').one()
        self.assertEqual(grp2.name, grp.name)
        self.assertEqual(grp2.description, grp.description)

    def test_group_edit(self):
        grp = Group(name='test_grp_name', description='test group')
        with SessionScope(db):
            db.session.add(grp)
            db.session.commit()

        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        improved_grp = Group(name='changed_name', description='Updated')
        rv = self.client.put('/api/group/{}'.format('test_grp_name'),
                          content_type='application/json',
                          data=json.dumps(improved_grp.as_json()))
        self.assert200(rv)

        # Pull the posted group
        grp2 = Group.query.one()
        self.assertEqual(grp2.name, improved_grp.name)
        self.assertEqual(grp2.description, improved_grp.description)

    def test_user_no_groups(self):
        self.login()
        rv = self.client.get('/api/user/{}/groups'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEqual(len(rv.json['groups']), 0)

    def test_user_groups(self):
        grp1 = Group(name='test_1')
        grp2 = Group(name='test_2')
        self.test_user.groups.append(grp1)
        self.test_user.groups.append(grp2)
        with SessionScope(db):
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        self.login()
        rv = self.client.get('/api/user/{}/groups'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEqual(len(rv.json['groups']), 2)

    def test_put_user_groups(self):
        grp1 = Group(name='test1')
        grp2 = Group(name='test2')
        self.test_user.groups.append(grp1)
        with SessionScope(db):
            db.session.add(grp2)
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)

        # initially grp 1 is the only for the user
        self.assertEqual(self.test_user.groups[0].name, 'test1')
        grp2 = db.session.merge(grp2)

        # put only the 2nd group, should end up being the only one for the user
        self.login()
        rv = self.client.put('/api/user/{}/groups'.format(TEST_USER_ID),
                          content_type='application/json',
                          data=json.dumps({'groups': [grp2.as_json()]}))
        self.assert200(rv)
        self.assertEqual(len(self.test_user.groups), 1)
        self.assertEqual(self.test_user.groups[0].name, 'test2')
