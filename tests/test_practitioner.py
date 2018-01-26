"""Unit test module for Practitioner module"""
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.practitioner import Practitioner
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
