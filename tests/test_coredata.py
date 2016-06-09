"""Coredata tests"""
from datetime import datetime
from flask_webtest import SessionScope
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.coredata import Coredata
from portal.models.organization import Organization
from portal.models.role import ROLE
from portal.models.tou import ToU


class TestCoredata(TestCase):

    def bless_with_basics(self):
        """Bless test user with basic requirements"""
        self.test_user.birthdate = datetime.utcnow()

        # Register with a clinic
        org = Organization(name='fake urology clinic')
        self.test_user.organizations.append(org)

        # Agree to Terms of Use
        audit = Audit(user_id=TEST_USER_ID)
        tou = ToU(audit=audit, text="filler text")
        with SessionScope(db):
            db.session.add(tou)
            db.session.commit()

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
        self.assertTrue(Coredata().initial_obtained(self.test_user))
