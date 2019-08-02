"""Unit test module for Encounter API and model"""

import json
import os
import time

import dateutil
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.encounter import Encounter
from portal.models.organization import Organization
from portal.models.role import ROLE
from portal.models.user import INVITE_PREFIX
from tests import TEST_USER_ID, TestCase


class TestEncounter(TestCase):

    def test_encounter_from_fhir(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'encounter-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        enc = Encounter.from_fhir(data)
        assert enc.status == 'finished'
        assert enc.auth_method == 'password_authenticated'
        assert enc.start_time == dateutil.parser.parse("2013-05-05")

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
        assert enc.status == data['status']
        assert enc.auth_method == data['auth_method']

    def test_encounter_on_login(self):
        self.login()
        assert len(self.test_user.encounters) == 1
        assert (self.test_user.current_encounter.auth_method
                == 'password_authenticated')

    def test_encounter_after_logout(self):
        self.login()
        time.sleep(0.1)
        self.login()  # generate a second encounter - should logout the first
        self.client.get('/logout', follow_redirects=True)
        assert len(self.test_user.encounters) > 1
        assert all(e.status == 'finished' for e in self.test_user.encounters)
        # as we generate failsafe on missing, confirm that's the type returned
        assert self.test_user.current_encounter.auth_method == 'failsafe'

    def test_service_encounter_on_login(self):
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)
        assert (service_user.current_encounter.auth_method
                == 'service_token_authenticated')

    def test_login_as(self):
        self.bless_with_basics()
        self.promote_user(role_name=ROLE.WRITE_ONLY.value)
        self.test_user = db.session.merge(self.test_user)
        consented_org = self.test_user.valid_consents[0].organization_id
        staff_user = self.add_user(username='staff@example.com')
        staff_user.organizations.append(Organization.query.get(consented_org))
        self.promote_user(user=staff_user, role_name=ROLE.STAFF.value)
        staff_user = db.session.merge(staff_user)
        self.login(user_id=staff_user.id)
        assert staff_user.current_encounter

        # Switch to test_user using login_as, test the encounter
        self.test_user = db.session.merge(self.test_user)
        response = self.client.get('/login-as/{}'.format(TEST_USER_ID))
        assert response.status_code == 302  # sent to next_after_login
        assert (self.test_user.current_encounter.auth_method
                == 'staff_authenticated')
        assert self.test_user._email.startswith(INVITE_PREFIX)

    def test_login_as_bogus(self):
        self.bless_with_basics(make_patient=False)
        self.promote_user(role_name=ROLE.STAFF.value)
        self.test_user = db.session.merge(self.test_user)
        consented_org = self.test_user.valid_consents[0].organization_id
        staff_user = self.add_user(username='staff@example.com')
        staff_user.organizations.append(Organization.query.get(consented_org))
        self.promote_user(user=staff_user, role_name=ROLE.ADMIN.value)
        self.promote_user(user=staff_user, role_name=ROLE.STAFF.value)
        staff_user = db.session.merge(staff_user)
        self.login(user_id=staff_user.id)
        assert staff_user.current_encounter

        # Switch to test_user using login_as, test the encounter
        self.test_user = db.session.merge(self.test_user)
        response = self.client.get('/login-as/{}'.format(TEST_USER_ID))
        # should return 401 as test user isn't a patient or partner
        assert response.status_code == 401
        assert self.test_user.current_encounter.auth_method == 'failsafe'
        assert staff_user.current_encounter

    def test_failsafe(self):
        self.bless_with_basics()
        self.promote_user(role_name=ROLE.WRITE_ONLY.value)
        self.test_user = db.session.merge(self.test_user)
        consented_org = self.test_user.valid_consents[0].organization_id
        staff_user = self.add_user(username='staff@example.com')
        staff_user.organizations.append(Organization.query.get(consented_org))
        self.promote_user(user=staff_user, role_name=ROLE.STAFF.value)
        staff_user = db.session.merge(staff_user)
        self.login(user_id=staff_user.id)
        assert staff_user.current_encounter

        # Switch to test_user using login_as, test the encounter
        self.test_user = db.session.merge(self.test_user)
        response = self.client.get('/login-as/{}'.format(TEST_USER_ID))
        assert response.status_code == 302  # sent to next_after_login
        assert (self.test_user.current_encounter.auth_method
                == 'staff_authenticated')
        assert self.test_user._email.startswith(INVITE_PREFIX)

        # Blow away test user's current encounter, and confirm a failsafe
        # comes to life
        e = Encounter.query.filter(Encounter.user_id == TEST_USER_ID).one()
        db.session.delete(e)

        self.test_user = db.session.merge(self.test_user)
        encounter = self.test_user.current_encounter
        assert encounter.auth_method == 'failsafe'
        assert encounter.status == 'in-progress'
