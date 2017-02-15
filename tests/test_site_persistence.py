"""Tests module for site persistence

Difficult scenario to test - want to confirm we can read in a site
from a persistence file, and see proper function of a few high level
integration tests.  For example, does a complicated strategy come
to life and properly control the visiblity of a intervention card?

"""
from flask_webtest import SessionScope
import os
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.site_persistence import SitePersistence
from portal.models.audit import Audit
from portal.models.fhir import CC
from portal.models.intervention import INTERVENTION
from portal.models.organization import Organization
from portal.models.app_text import app_text

known_good_persistence_file =\
"https://raw.githubusercontent.com/uwcirg/TrueNTH-USA-site-config/b42b4f9fda85fd9484b3d68145813de190a0c9c8/site_persistence_file.json"


class TestSitePersistence(TestCase):

    def setUp(self):
        super(TestSitePersistence, self).setUp()
        if os.environ.get('PERSISTENCE_FILE'):
            self.fail("unset environment var PERSISTENCE_FILE for test")
        self.app.config['PERSISTENCE_FILE'] = known_good_persistence_file
        SitePersistence().import_(
            include_interventions=True, keep_unmentioned=False)

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
        user = self.test_user
        self.assertFalse(
            INTERVENTION.DECISION_SUPPORT_P3P.display_for_user(user).access)

        # Fulfill conditions
        self.add_procedure(
            code='424313000', display='Started active surveillance')
        user.save_constrained_observation(
            codeable_concept=CC.PCaLocalized, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID))
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
            INTERVENTION.SELF_MANAGEMENT.description, 'Symptom Tracker')
        self.assertEquals(
            INTERVENTION.SELF_MANAGEMENT.link_label, 'Go to Symptom Tracker')

    def test_app_text(self):
        self.assertEquals(app_text('landing title'), 'Welcome to TrueNTH')
