"""Unit test module for Practitioner module"""
from flask_webtest import SessionScope
import json

from portal.extensions import db
from portal.models.practitioner import Practitioner
from portal.models.role import ROLE
from tests import TestCase


class TestPractitioner(TestCase):
    """Practitioner model and view tests"""

    def test_practitioner_search(self):
        pract1 = Practitioner(first_name="Indiana", last_name="Jones")
        pract2 = Practitioner(first_name="John", last_name="Watson")
        pract3 = Practitioner(first_name="John", last_name="Zoidberg")
        with SessionScope(db):
            db.session.add(pract1)
            db.session.add(pract2)
            db.session.add(pract3)
            db.session.commit()

        self.login()

        # test base query
        resp = self.client.get('/api/practitioner')
        self.assert200(resp)

        self.assertEqual(resp.json['total'], 3)
        self.assertEqual(resp.json['entry'][0]['name']['given'], 'Indiana')

        # test query with multiple results
        resp = self.client.get('/api/practitioner?first_name=John')
        self.assert200(resp)

        self.assertEqual(resp.json['total'], 2)
        self.assertEqual(resp.json['entry'][0]['name']['family'], 'Watson')

        # test query with multiple search parameters
        resp = self.client.get(
            '/api/practitioner?first_name=John&last_name=Zoidberg')
        self.assert200(resp)

        self.assertEqual(resp.json['total'], 1)
        self.assertEqual(resp.json['entry'][0]['name']['family'], 'Zoidberg')

    def test_practitioner_get(self):
        pract = Practitioner(first_name="Indiana", last_name="Jones")
        with SessionScope(db):
            db.session.add(pract)
            db.session.commit()
        pract = db.session.merge(pract)

        pract.phone = '555-1234'

        resp = self.client.get('/api/practitioner/{}'.format(pract.id))
        self.assert200(resp)

        self.assertEqual(resp.json['resourceType'], 'Practitioner')
        self.assertEqual(resp.json['name']['given'], 'Indiana')
        self.assertEqual(len(resp.json['telecom']), 1)
        cp_json = resp.json['telecom'][0]
        self.assertEqual(cp_json['system'], 'phone')
        self.assertEqual(cp_json['use'], 'work')
        self.assertEqual(cp_json['value'], '555-1234')

    def test_practitioner_post(self):
        data = {
            'resourceType': 'Practitioner',
            'name': {
                'given': 'John',
                'family': 'Zoidberg'
            },
            'telecom': [
                {
                    'system': 'phone',
                    'use': 'work',
                    'value': '555-1234'
                }
            ]
        }

        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        resp = self.client.post('/api/practitioner', data=json.dumps(data),
                                content_type='application/json')
        self.assert200(resp)

        self.assertEqual(Practitioner.query.count(), 1)
        pract = Practitioner.query.all()[0]
        self.assertEqual(pract.last_name, 'Zoidberg')
        self.assertEqual(pract.phone, '555-1234')
