"""Unit test module for Encounter API and model"""
import dateutil
import json
import os
from tests import TestCase, TEST_USER_ID
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.encounter import Encounter


class TestEncounter(TestCase):

    def test_encounter_from_fhir(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'encounter-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        enc = Encounter.from_fhir(data)
        self.assertEquals(enc.status, 'finished')
        self.assertEquals(enc.auth_method, 'password_authenticated')
        self.assertEquals(enc.start_time, dateutil.parser.parse("2013-05-05"))

    def test_encounter_as_fhir(self):
        enc = Encounter(status='planned', auth_method='url_authenticated',
                        user_id=TEST_USER_ID,
                        start_time=dateutil.parser.parse("2013-07-07"))
        data = enc.as_fhir()
        # confirm we can store
        with SessionScope(db):
            db.session.add(enc)
            db.session.commit()
        enc = db.session.merge(enc)
        self.assertEquals(enc.status, data['status'])
        self.assertEquals(enc.auth_method, data['auth_method'])

    def test_encounter_on_login(self):
        self.login()
        self.assertTrue(self.test_user.encounters.count() > 0)
        self.assertEquals(
            self.test_user.current_encounter.auth_method,
            'password_authenticated')

    def test_encounter_after_logout(self):
        self.login()
        self.client.get('/logout', follow_redirects=True)
        self.assertTrue(self.test_user.encounters.count() > 0)
        self.assertFalse(self.test_user.current_encounter)

    def test_service_encounter_on_login(self):
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)
        self.assertTrue(service_user.encounters.count() > 0)
        self.assertEquals(
            service_user.current_encounter.auth_method,
            'service_token_authenticated')
