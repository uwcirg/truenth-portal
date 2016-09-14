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
        self.assertTrue(Organization.query.count() > 5)
        npis = []
        for org in Organization.query:
            npis += [id.value for id in org.identifiers if id.system ==
                   'http://hl7.org/fhir/sid/us-npi']
        self.assertTrue('1447420906' in npis)  # UWMC
        self.assertTrue('1164512851' in npis)  # UCSF

    def testP3Pstrategy(self):
        # Prior to meeting conditions in strategy, user shouldn't have access
        # (provided we turn off public access)
        INTERVENTION.DECISION_SUPPORT_P3P.public_access = False
        INTERVENTION.SEXUAL_RECOVERY.public_access = False # part of strat.
        user = self.add_user(username=TEST_USERNAME)
        self.assertFalse(
            INTERVENTION.DECISION_SUPPORT_P3P.display_for_user(user).access)

        # Fulfill conditions
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
        self.assertTrue(
            INTERVENTION.DECISION_SUPPORT_P3P.display_for_user(user).access)

    def test_interventions(self):
        """Portions of the interventions migrated"""
        # confirm we see a sample of changes from the
        # defauls in add_static_interventions call
        # to what's expected in the persistence file
        self.assertEquals(
            INTERVENTION.CARE_PLAN.card_html, ('<p>Organization and '
            'support for the many details of life as a prostate cancer '
            'survivor</p>'))
        self.assertEquals(
            INTERVENTION.SELF_MANAGEMENT.description, 'Symptom Tracker tool')
        self.assertEquals(
            INTERVENTION.SELF_MANAGEMENT.link_label, 'Go to Symptom Tracker')
