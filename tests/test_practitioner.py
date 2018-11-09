"""Unit test module for Practitioner module"""
from __future__ import unicode_literals  # isort:skip

import json

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.practitioner import Practitioner
from portal.models.role import ROLE
from portal.system_uri import US_NPI
from tests import TestCase


class TestPractitioner(TestCase):
    """Practitioner model and view tests"""

    def test_practitioner_search(self):
        pract1 = self.add_practitioner(
            first_name="Indiana", last_name="Jones", id_value='ijones')
        pract2 = self.add_practitioner(
            first_name="John", last_name="Watson", id_value='jwatson')
        pract3 = self.add_practitioner(
            first_name="John", last_name="Zoidberg", id_value='jzoidberg')

        self.login()

        # test base query
        resp = self.client.get('/api/practitioner')
        assert resp.status_code == 200

        assert resp.json['total'] == 3
        assert resp.json['entry'][0]['name'][0]['given'] == 'Indiana'

        # test query with multiple results
        resp = self.client.get('/api/practitioner?first_name=John')
        assert resp.status_code == 200

        assert resp.json['total'] == 2
        assert resp.json['entry'][0]['name'][0]['family'] == 'Watson'

        # test query with multiple search parameters
        resp = self.client.get('/api/practitioner', query_string={
            'first_name': 'John',
            'last_name': 'Zoidberg',
            'patch_dstu2': True})
        assert resp.status_code == 200

        assert resp.json['total'] == 1
        resource = resp.json['entry'][0]['resource']
        assert resource['name'][0]['family'] == 'Zoidberg'

        # test query using identifier system/value
        resp = self.client.get(
            '/api/practitioner?system={}&value=ijones'.format(US_NPI))
        assert resp.status_code == 200

        assert resp.json['total'] == 1
        assert resp.json['entry'][0]['name'][0]['family'] == 'Jones'

        # test invalid system/value combos
        resp = self.client.get(
            '/api/practitioner?system=testsys')
        assert resp.status_code == 400

        resp = self.client.get(
            '/api/practitioner?system=testsys&value=notvalid')
        assert resp.status_code == 404

    def test_practitioner_get(self):
        pract = self.add_practitioner(first_name="Indiana", last_name="Jones")
        pract.phone = '555-1234'
        pract.email = 'test@notarealsite.com'
        self.add_practitioner(
            first_name="John", last_name="Watson", id_value='jwatson')
        pract = db.session.merge(pract)

        # test get by ID
        self.login()
        resp = self.client.get('/api/practitioner/{}'.format(pract.id))
        assert resp.status_code == 200

        assert resp.json['resourceType'] == 'Practitioner'
        assert resp.json['name'][0]['given'] == 'Indiana'
        phone_json = {'system': 'phone', 'use': 'work', 'value': '555-1234'}
        assert phone_json in resp.json['telecom']
        email_json = {'system': 'email', 'value': 'test@notarealsite.com'}
        assert email_json in resp.json['telecom']

        # test get by external identifier
        resp = self.client.get(
            '/api/practitioner/{}?system={}'.format('jwatson', US_NPI))
        assert resp.status_code == 200

        assert resp.json['resourceType'] == 'Practitioner'
        assert resp.json['name'][0]['family'] == 'Watson'

        # test with invalid external identifier
        resp = self.client.get(
            '/api/practitioner/{}?system={}'.format('invalid', 'testsys'))
        assert resp.status_code == 404

    def test_practitioner_post(self):
        data = {
            'resourceType': 'Practitioner',
            'name': [
                {
                    'given': 'John',
                    'family': 'Zoidberg'
                }
            ],
            'telecom': [
                {
                    'system': 'phone',
                    'use': 'work',
                    'value': '555-1234'
                },
                {
                    'system': 'email',
                    'value': 'test@notarealsite.com'
                }
            ],
            'identifier': [
                {
                    'system': 'testsys',
                    'value': 'testval'
                }
            ]
        }

        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()

        resp = self.client.post('/api/practitioner', data=json.dumps(data),
                                content_type='application/json')
        assert resp.status_code == 200

        assert Practitioner.query.count() == 1
        pract = Practitioner.query.all()[0]
        assert pract.last_name == 'Zoidberg'
        assert pract.email == 'test@notarealsite.com'
        assert pract.phone == '555-1234'
        assert len(pract.identifiers.all()) == 1
        assert pract.identifiers[0].system == 'testsys'

        # confirm audit entry for practitioner creation
        audit = Audit.query.first()
        audit_words = audit.comment.split()
        assert audit_words[0] == 'created'

        # test with existing external identifier
        data = {
            'resourceType': 'Practitioner',
            'name': [
                {
                    'given': 'John',
                    'family': 'Watson'
                }
            ],
            'identifier': [
                {
                    'system': 'testsys',
                    'value': 'testval'
                }
            ]
        }

        resp = self.client.post('/api/practitioner', data=json.dumps(data),
                                content_type='application/json')
        assert resp.status_code == 409

    def test_practitioner_put(self):
        pract = self.add_practitioner(first_name="John", last_name="Watson")
        pract.phone = '555-1234'
        pract.email = 'test1@notarealsite.com'
        pract2 = self.add_practitioner(
            first_name="Indiana", last_name="Jones", id_value='testval')
        pract, pract2 = map(db.session.merge, (pract, pract2))
        pract_id = pract.id
        pract2_id = pract2.id

        data = {
            'resourceType': 'Practitioner',
            'name': [
                {
                    'given': 'John',
                    'family': 'Zoidberg'
                }
            ],
            'telecom': [
                {
                    'system': 'phone',
                    'use': 'work',
                    'value': '555-9876'
                },
                {
                    'system': 'email',
                    'value': 'test2@notarealsite.com'
                }
            ]
        }

        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()

        # test update by ID
        resp = self.client.put('/api/practitioner/{}'.format(pract_id),
                               data=json.dumps(data),
                               content_type='application/json')
        assert resp.status_code == 200

        updated = Practitioner.query.get(pract_id)
        assert updated.last_name == 'Zoidberg'
        assert updated.phone == '555-9876'
        assert updated.email == 'test2@notarealsite.com'

        # confirm audit entry for practitioner update
        audit = Audit.query.first()
        audit_words = audit.comment.split()
        assert audit_words[0] == 'updated'

        # test update by external identifier
        data = {
            'resourceType': 'Practitioner',
            'telecom': [
                {
                    'system': 'phone',
                    'use': 'work',
                    'value': '999-9999'
                }
            ]
        }

        resp = self.client.put(
            '/api/practitioner/{}?system={}'.format('testval', US_NPI),
            data=json.dumps(data),
            content_type='application/json')
        assert resp.status_code == 200

        updated = Practitioner.query.get(pract2_id)
        assert updated.last_name == 'Jones'
        assert updated.phone == '999-9999'

        # test with invalid external identifier
        resp = self.client.put(
            '/api/practitioner/{}?system={}'.format('invalid', 'testsys'),
            data=json.dumps(data),
            content_type='application/json')
        assert resp.status_code == 404

        # test with existing external identifier
        data = {
            'resourceType': 'Practitioner',
            'identifier': [
                {
                    'system': US_NPI,
                    'value': 'testval'
                }
            ]
        }

        resp = self.client.put('/api/practitioner/{}'.format(pract_id),
                               data=json.dumps(data),
                               content_type='application/json')
        assert resp.status_code == 409

        # test updating with same external identifier
        resp = self.client.put(
            '/api/practitioner/{}?system={}'.format('testval', US_NPI),
            data=json.dumps(data),
            content_type='application/json')
        assert resp.status_code == 200
