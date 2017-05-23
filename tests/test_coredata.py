"""Coredata tests"""
from flask_webtest import SessionScope
from tests import TestCase

from portal.extensions import db
from portal.models.coredata import Coredata
from portal.models.role import ROLE


class TestCoredata(TestCase):

    def test_registry(self):
        self.assertTrue(len(Coredata()._registered) > 1)

    def test_partner(self):
        """Partner doesn't need dx etc., set min and check pass"""
        self.bless_with_basics()
        self.promote_user(role_name=ROLE.PARTNER)
        self.test_user = db.session.merge(self.test_user)
        self.assertTrue(Coredata().initial_obtained(self.test_user))

    def test_patient(self):
        """Patient has additional requirements"""
        self.bless_with_basics()
        self.promote_user(role_name=ROLE.PATIENT)
        self.test_user = db.session.merge(self.test_user)
        # Prior to adding clinical data, should return false
        self.assertFalse(Coredata().initial_obtained(self.test_user))

        self.add_required_clinical_data()
        with SessionScope(db):
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        # should leave only indigenous, race and ethnicity as options
        # and nothing required
        self.assertTrue(Coredata().initial_obtained(self.test_user))
        expect = set(('race', 'ethnicity', 'indigenous'))
        found = set(Coredata().optional(self.test_user))
        self.assertEquals(found, expect)

    def test_still_needed(self):
        """Query for list of missing datapoints in legible format"""
        self.promote_user(role_name=ROLE.PATIENT)
        self.test_user = db.session.merge(self.test_user)

        needed = Coredata().still_needed(self.test_user)
        self.assertTrue(len(needed) > 1)
        self.assertTrue('dob' in needed)
        self.assertTrue('tou' in needed)
        self.assertTrue('clinical' in needed)
        self.assertTrue('org' in needed)

        # needed should match required (minus 'name', 'role')
        required = Coredata().required(self.test_user)
        self.assertEquals(set(required) - set(needed), set(('name', 'role')))
