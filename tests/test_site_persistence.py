"""Tests module for site persistence

Difficult scenario to test - want to confirm we can read in a site
from a persistence file, and see proper function of a few high level
integration tests.  For example, does a complicated strategy come
to life and properly control the visibility of a intervention card?

"""

from datetime import datetime
import os

from flask_webtest import SessionScope
import pytest

from portal.config.site_persistence import SitePersistence
from portal.extensions import db
from portal.models.app_text import app_text
from portal.models.audit import Audit
from portal.models.clinical_constants import CC
from portal.models.encounter import Encounter
from portal.models.intervention import INTERVENTION
from portal.models.organization import Organization
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
    QuestionnaireBankQuestionnaire,
)
from portal.models.recur import Recur
from portal.models.research_protocol import ResearchProtocol
from portal.models.role import ROLE
from portal.models.user import User
from tests import TEST_USER_ID, TestCase


class TestSitePersistence(TestCase):

    def setUp(self):
        super(TestSitePersistence, self).setUp()
        # Tests currently expect 'gil' version of persistence
        self.app.config['PERSISTENCE_DIR'] = 'gil'
        SitePersistence(target_dir=None).import_(keep_unmentioned=False)

    def tearDown(self):
        if hasattr(self, 'tmpfile') and self.tmpfile:
            os.remove(self.tmpfile)
            del self.tmpfile
        super(TestSitePersistence, self).tearDown()

    def testOrgs(self):
        """Confirm persisted organizations came into being"""
        assert Organization.query.count() > 5
        npis = []
        for org in Organization.query:
            npis += [
                id.value for id in org.identifiers if id.system ==
                'http://hl7.org/fhir/sid/us-npi']
        assert '1447420906' in npis  # UWMC
        assert '1164512851' in npis  # UCSF

    def testMidLevelOrgDeletion(self):
        """Test for problem scenario where mid level org should be removed"""
        Organization.query.delete()
        self.deepen_org_tree()

        # with deep (test) org tree in place, perform a delete by
        # repeating import w/o keep_unmentioned set
        SitePersistence(target_dir=None).import_(keep_unmentioned=False)

    def testP3Pstrategy(self):
        # Prior to meeting conditions in strategy, user shouldn't have access
        # (provided we turn off public access)
        INTERVENTION.DECISION_SUPPORT_P3P.public_access = False
        INTERVENTION.SEXUAL_RECOVERY.public_access = False  # part of strat.
        user = self.test_user
        assert not INTERVENTION.DECISION_SUPPORT_P3P.display_for_user(
            user).access

        # Fulfill conditions
        enc = Encounter(status='in-progress', auth_method='url_authenticated',
                        user_id=TEST_USER_ID, start_time=datetime.utcnow())
        with SessionScope(db):
            db.session.add(enc)
            db.session.commit()
        self.add_procedure(
            code='424313000', display='Started active surveillance')
        User.query.get(TEST_USER_ID).save_observation(
            codeable_concept=CC.PCaLocalized, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
            status=None, issued=None)
        self.promote_user(user, role_name=ROLE.PATIENT.value)
        with SessionScope(db):
            db.session.commit()
        user = db.session.merge(user)

        # P3P strategy should now be in view for test user
        assert INTERVENTION.DECISION_SUPPORT_P3P.display_for_user(user).access

    def test_interventions(self):
        """Portions of the interventions migrated"""
        # confirm we see a sample of changes from the
        # defauls in add_static_interventions call
        # to what's expected in the persistence file
        assert (INTERVENTION.CARE_PLAN.card_html == (
            '<p>Organization and support for the many details of life as a '
            'prostate cancer survivor</p>'))
        assert INTERVENTION.SELF_MANAGEMENT.description == 'Symptom Tracker'
        assert (INTERVENTION.SELF_MANAGEMENT.link_label
                == 'Go to Symptom Tracker')

    def test_app_text(self):
        assert app_text('landing title') == 'Welcome to TrueNTH'

    @pytest.mark.skip(reason="QBs no longer support multiple recurrences")
    def test_questionnaire_banks_recurs(self):
        # only one recurrence per qb allowed at this time
        initial_recur = Recur(
            start='{"days": 90}', cycle_length='{"days": 90}',
            termination='{"days": 720}')
        every_six_thereafter = Recur(
            start='{"days": 720}', cycle_length='{"days": 180}')

        rp = ResearchProtocol(name='proto')
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        metastatic_org = Organization(name='metastatic')
        metastatic_org.research_protocols.append(rp)
        questionnaire = self.add_questionnaire(name='test_q')
        with SessionScope(db):
            db.session.add(initial_recur)
            db.session.add(every_six_thereafter)
            db.session.add(metastatic_org)
            db.session.add(questionnaire)
            db.session.commit()

        initial_recur = db.session.merge(initial_recur)
        every_six_thereafter = db.session.merge(every_six_thereafter)

        # with bits in place, setup a recurring QB
        recurs = [initial_recur, every_six_thereafter]
        mr_qb = QuestionnaireBank(
            name='metastatic_recurring',
            classification='recurring',
            research_protocol_id=rp_id,
            start='{"days": 0}', overdue='{"days": 1}',
            expired='{"days": 30}',
            recurs=recurs)
        questionnaire = db.session.merge(questionnaire)

        qbq = QuestionnaireBankQuestionnaire(
            questionnaire=questionnaire, rank=1)
        mr_qb.questionnaires.append(qbq)
        with SessionScope(db):
            db.session.add(mr_qb)
            db.session.commit()
        mr_qb, initial_recur, every_six_thereafter = map(
            db.session.merge, (mr_qb, initial_recur, every_six_thereafter))

        # confirm persistence of this questionnaire bank includes the bits
        # added above
        results = mr_qb.as_json()

        copy = QuestionnaireBank.from_json(results)
        assert copy.name == mr_qb.name
        assert copy.recurs == [initial_recur, every_six_thereafter]

        # now, modify the persisted form, remove one recur and add another
        new_recur = Recur(
            start='{"days": 900}',
            cycle_length='{"days": 180}',
            termination='{"days": 1800}')
        results['recurs'] = [
            initial_recur.as_json(), new_recur.as_json()]
        updated_copy = QuestionnaireBank.from_json(results)

        assert ([r.as_json() for r in updated_copy.recurs]
                == [r.as_json() for r in (initial_recur, new_recur)])


class TestEpromsSitePersistence(TestCase):

    def setUp(self):
        super(TestEpromsSitePersistence, self).setUp()
        # Tests currently expect 'eproms' version of persistence
        self.app.config['PERSISTENCE_DIR'] = 'eproms'
        SitePersistence(target_dir=None).import_(keep_unmentioned=False)

    def testOrgs(self):
        """Confirm persisted organizations came into being"""
        assert Organization.query.count() > 5
        tngr = Organization.query.filter(
            Organization.name == 'TrueNTH Global Registry').one()
        assert tngr.id == 10000
