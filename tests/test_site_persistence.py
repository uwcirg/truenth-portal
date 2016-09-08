"""Tests module for site persistence

Difficult scenario to test - want to confirm we can read in a site
from a persistence file, and see proper function of a few high level
integration tests.  For example, does a complicated strategy come
to life and properly control the visiblity of a intervention card?

"""
from flask_webtest import SessionScope
from tests import TestCase, TEST_USER_ID, TEST_USERNAME

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.fhir import CC
from portal.models.intervention import INTERVENTION
from portal.models.organization import Organization
from manage import initdb


class TestSitePersistence(TestCase):

    def setUp(self):
        """Specialize to perform a seed and persistence approach"""
        initdb()

    def testOrgs(self):
        """Confirm persisted organizations came into being"""
        self.assertEquals(Organization.query.count(), 6)
        npis = []
        for org in Organization.query:
            npis += [id.value for id in org.identifiers if id.system ==
                   'http://hl7.org/fhir/sid/us-npi']
        self.assertTrue('1447420906' in npis)  # UWMC
        self.assertTrue('1164512851' in npis)  # UCSF

    def testP3Pstrategy(self):

        user = self.add_user(username=TEST_USERNAME)
        user.add_organization('UW Medicine (University of Washington)')
        user.save_constrained_observation(
            codeable_concept=CC.TX, value_quantity=CC.FALSE_VALUE,
            audit=Audit(user_id=TEST_USER_ID))
        user.save_constrained_observation(
            codeable_concept=CC.PCaLocalized, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID))
        with SessionScope(db):
            db.session.commit()
        user = db.session.merge(user)

        # P3P strategy should now be in view for test user
        ds_p3p = INTERVENTION.DECISION_SUPPORT_P3P
        self.assertTrue(ds_p3p.display_for_user(user).access)

