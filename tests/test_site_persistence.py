"""Tests module for site persistence

Difficult scenario to test - want to confirm we can read in a site
from a persistence file, and see proper function of a few high level
integration tests.  For example, does a complicated strategy come
to life and properly control the visiblity of a intervention card?

"""
from datetime import datetime
from flask_webtest import SessionScope
import os
from tests import TestCase, TEST_USER_ID
from tests.test_assessment_status import mock_questionnairebanks
from tempfile import NamedTemporaryFile

from portal.extensions import db
from portal.site_persistence import SitePersistence
from portal.models.app_text import app_text
from portal.models.audit import Audit
from portal.models.encounter import Encounter
from portal.models.fhir import CC
from portal.models.intervention import INTERVENTION
from portal.models.organization import Organization
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.questionnaire_bank import QuestionnaireBankQuestionnaire
from portal.models.recur import Recur
from portal.models.role import ROLE
from portal.models.user import get_user

revision = '66cd2c5e392cd499b5cc4f36dff95d8ec45f14c7'
known_good_persistence_file = (
    "https://raw.githubusercontent.com/uwcirg/TrueNTH-USA-site-config/{}"
    "/site_persistence_file.json".format(revision))


class TestSitePersistence(TestCase):

    def setUp(self):
        super(TestSitePersistence, self).setUp()
        if os.environ.get('PERSISTENCE_FILE'):
            self.fail("unset environment var PERSISTENCE_FILE for test")
        self.app.config['PERSISTENCE_FILE'] = known_good_persistence_file
        SitePersistence().import_(
            exclude_interventions=False, keep_unmentioned=False)

    def tearDown(self):
        if hasattr(self, 'tmpfile') and self.tmpfile:
            os.remove(self.tmpfile)
            del self.tmpfile

    def testOrgs(self):
        """Confirm persisted organizations came into being"""
        self.assertTrue(Organization.query.count() > 5)
        npis = []
        for org in Organization.query:
            npis += [
                id.value for id in org.identifiers if id.system ==
                'http://hl7.org/fhir/sid/us-npi']
        self.assertTrue('1447420906' in npis)  # UWMC
        self.assertTrue('1164512851' in npis)  # UCSF

    def testMidLevelOrgDeletion(self):
        """Test for problem scenario where mid level org should be removed"""
        Organization.query.delete()
        self.deepen_org_tree()

        # with deep (test) org tree in place, perform a delete by
        # repeating import w/o keep_unmentioned set
        SitePersistence().import_(
            exclude_interventions=False, keep_unmentioned=False)

    def testP3Pstrategy(self):
        # Prior to meeting conditions in strategy, user shouldn't have access
        # (provided we turn off public access)
        INTERVENTION.DECISION_SUPPORT_P3P.public_access = False
        INTERVENTION.SEXUAL_RECOVERY.public_access = False  # part of strat.
        user = self.test_user
        self.assertFalse(
            INTERVENTION.DECISION_SUPPORT_P3P.display_for_user(user).access)

        # Fulfill conditions
        enc = Encounter(status='in-progress', auth_method='url_authenticated',
                        user_id=TEST_USER_ID, start_time=datetime.utcnow())
        with SessionScope(db):
            db.session.add(enc)
            db.session.commit()
        self.add_procedure(
            code='424313000', display='Started active surveillance')
        get_user(TEST_USER_ID).save_constrained_observation(
            codeable_concept=CC.PCaLocalized, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID))
        self.promote_user(user, role_name=ROLE.PATIENT)
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
            INTERVENTION.CARE_PLAN.card_html,
            ('<p>Organization and '
             'support for the many details of life as a prostate cancer '
             'survivor</p>'))
        self.assertEquals(
            INTERVENTION.SELF_MANAGEMENT.description, 'Symptom Tracker')
        self.assertEquals(
            INTERVENTION.SELF_MANAGEMENT.link_label, 'Go to Symptom Tracker')

    def test_app_text(self):
        self.assertEquals(app_text('landing title'), 'Welcome to TrueNTH')

    def test_questionnaire_banks_recurs(self):
        # set up a few recurring instances
        initial_recur = Recur(
            days_to_start=90, days_in_cycle=90,
            days_till_termination=720)
        every_six_thereafter = Recur(
            days_to_start=720, days_in_cycle=180)

        metastatic_org = Organization(name='metastatic')
        questionnaire = Questionnaire(name='test_q')
        with SessionScope(db):
            db.session.add(initial_recur)
            db.session.add(every_six_thereafter)
            db.session.add(metastatic_org)
            db.session.add(questionnaire)
            db.session.commit()

        initial_recur = db.session.merge(initial_recur)
        every_six_thereafter = db.session.merge(every_six_thereafter)
        metastatic_org_id = db.session.merge(metastatic_org).id

        # with bits in place, setup a recurring QB
        mr_qb = QuestionnaireBank(
            name='metastatic_recurring',
            classification='recurring',
            organization_id=metastatic_org_id)
        questionnaire = db.session.merge(questionnaire)
        recurs = [initial_recur, every_six_thereafter]

        qbq = QuestionnaireBankQuestionnaire(
            questionnaire=questionnaire,
            days_till_due=1, days_till_overdue=30,
            rank=1, recurs=recurs)
        mr_qb.questionnaires.append(qbq)

        # confirm persistence of this questionnaire bank includes the bits
        # added above
        results = mr_qb.as_json()

        copy = QuestionnaireBank.from_json(results)
        self.assertEquals(copy.name, mr_qb.name)
        copy_q = copy.questionnaires[0]
        self.assertEquals(copy_q.recurs, [initial_recur, every_six_thereafter])

        # now, modify the persisted form, remove one recur and add another
        new_recur = Recur(
            days_to_start=900, days_in_cycle=180, days_till_termination=1800)
        results['questionnaires'][0]['recurs'] = [
            initial_recur.as_json(), new_recur.as_json()]
        updated_copy = QuestionnaireBank.from_json(results)

        self.assertEquals(
            [r.as_json() for r in updated_copy.questionnaires[0].recurs],
            [r.as_json() for r in (initial_recur, new_recur)])

    def test_questionnaire_banks(self):
        mock_questionnairebanks('eproms')

        def mock_file(read_only=True):
            '''mock version to create local testfile for site_persistence'''
            if not hasattr(self, 'tmpfile'):
                with NamedTemporaryFile(mode='w', delete=False) as tmpfile:
                    self.tmpfile = tmpfile.name
            return self.tmpfile

        sp = SitePersistence()
        sp.persistence_filename = mock_file
        sp.export()
        with open(self.tmpfile) as f:
            data = f.read()
        self.assertTrue('recur' in data)

        # Pull same data back in
        sp.import_(exclude_interventions=True, keep_unmentioned=False)
