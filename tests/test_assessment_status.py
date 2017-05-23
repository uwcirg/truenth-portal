"""Module to test assessment_status"""
from datetime import datetime
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.assessment_status import AssessmentStatus
from portal.models.organization import Organization
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.questionnaire_bank import QuestionnaireBankQuestionnaire
from portal.models.fhir import QuestionnaireResponse
from tests import TestCase, TEST_USER_ID


def mock_qr(user_id, instrument_id, status='completed'):
    today = datetime.utcnow()
    qr_document = {
        "questionnaire": {
            "display": "Additional questions",
            "reference":
            "https://{}/api/questionnaires/{}".format(
                'SERVER_NAME', instrument_id)
        }
    }
    qr = QuestionnaireResponse(
        subject_id=TEST_USER_ID,
        status=status,
        authored=today,
        document=qr_document)
    with SessionScope(db):
        db.session.add(qr)
        db.session.commit()


localized_instruments = set(['eproms_add', 'epic26', 'comorb'])
metastatic_baseline_instruments = set(['eortc', 'ironmisc', 'factfpsi', 'epic26', 'prems'])
metastatic_indefinite_instruments = set(['irondemog'])

def mock_questionnairebanks():
    # Define test Orgs and QuestionnaireBanks for each group
    localized_org = Organization(name='localized')
    metastatic_org = Organization(name='metastatic')
    with SessionScope(db):
        db.session.add(localized_org)
        db.session.add(metastatic_org)
        db.session.commit()
    localized_org, metastatic_org = map(
        db.session.merge, (localized_org, metastatic_org))

    l_qb = QuestionnaireBank(
        name='localized',
        classification='baseline',
        organization_id=localized_org.id)
    mb_qb = QuestionnaireBank(
        name='metastatic',
        classification='baseline',
        organization_id=metastatic_org.id)
    mi_qb = QuestionnaireBank(
        name='metastatic_indefinite',
        classification='indefinite',
        organization_id=metastatic_org.id)
    for rank, instrument in enumerate(localized_instruments):
        q = Questionnaire(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(
            questionnaire=q, days_till_due=7, days_till_overdue=90,
            rank=rank)
        l_qb.questionnaires.append(qbq)
    for rank, instrument in enumerate(metastatic_baseline_instruments):
        q = Questionnaire(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(
            questionnaire=q, days_till_due=1, days_till_overdue=30,
            rank=rank)
        mb_qb.questionnaires.append(qbq)
    for rank, instrument in enumerate(metastatic_indefinite_instruments):
        q = Questionnaire(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(
            questionnaire=q, days_till_due=1, days_till_overdue=30,
            rank=rank)
        mi_qb.questionnaires.append(qbq)
    with SessionScope(db):
        db.session.add(l_qb)
        db.session.add(mb_qb)
        db.session.add(mi_qb)
        db.session.commit()

class TestAssessment(TestCase):

    def setUp(self):
        super(TestAssessment, self).setUp()
        mock_questionnairebanks()
        self.localized_org_id = Organization.query.filter_by(
            name='localized').one().id
        self.metastatic_org_id = Organization.query.filter_by(
            name='metastatic').one().id

    def mark_localized(self):
        self.test_user.organizations.append(Organization.query.get(
            self.localized_org_id))

    def mark_metastatic(self):
        self.test_user.organizations.append(Organization.query.get(
            self.metastatic_org_id))

    def test_localized_using_org(self):
        self.bless_with_basics()
        self.mark_localized()
        self.test_user = db.session.merge(self.test_user)

        # confirm appropriate instruments
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(
            set(a_s.instruments_needing_full_assessment('baseline')),
            localized_instruments)

        # check due date access
        for questionnaire in a_s.questionnaire_data.baseline():
            self.assertTrue(questionnaire.get('by_date') > datetime.utcnow())

        self.assertFalse(a_s.instruments_in_progress('baseline'))
        self.assertFalse(a_s.instruments_in_progress('all'))

    def test_localized_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26')
        mock_qr(user_id=TEST_USER_ID, instrument_id='comorb')

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "Completed")

        # confirm appropriate instruments
        self.assertFalse(a_s.instruments_needing_full_assessment('all'))
        self.assertFalse(a_s.instruments_in_progress('baseline'))

    def test_localized_inprogress_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='comorb',
                status='in-progress')

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "In Progress")

        # confirm appropriate instruments
        self.assertFalse(a_s.instruments_needing_full_assessment('all'))
        self.assertEquals(
            set(a_s.instruments_in_progress('baseline')), localized_instruments)

    def test_localized_in_process(self):
        # User finished one, time remains for other
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add')

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "In Progress")

        # confirm appropriate instruments
        self.assertEquals(
            localized_instruments -
            set(a_s.instruments_needing_full_assessment('all')),
            set(['eproms_add']))
        self.assertFalse(a_s.instruments_in_progress('baseline'))

    def test_metastatic_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        mock_qr(user_id=TEST_USER_ID, instrument_id='eortc')
        mock_qr(user_id=TEST_USER_ID, instrument_id='ironmisc')
        mock_qr(user_id=TEST_USER_ID, instrument_id='factfpsi')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26')
        mock_qr(user_id=TEST_USER_ID, instrument_id='prems')
        mock_qr(user_id=TEST_USER_ID, instrument_id='irondemog')

        self.mark_metastatic()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "Completed")

        # shouldn't need full or any inprocess
        self.assertFalse(a_s.instruments_needing_full_assessment('all'))
        self.assertFalse(a_s.instruments_in_progress('all'))

    def test_metastatic_due(self):
        # hasn't taken, but still in "Due" period
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_metastatic()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "Due")

        # confirm list of expected intruments needing attention
        a_s.instruments_needing_full_assessment('baseline')
        self.assertEquals(
            metastatic_baseline_instruments,
            set(a_s.instruments_needing_full_assessment('baseline')))
        self.assertFalse(a_s.instruments_in_progress('baseline'))

        # metastatic indefinite should also be 'due'
        self.assertEquals(
            metastatic_indefinite_instruments,
            set(a_s.instruments_needing_full_assessment('indefinite')))
        self.assertFalse(a_s.instruments_in_progress('indefinite'))

    def test_batch_lookup(self):
        self.login()
        self.bless_with_basics()
        rv = self.client.get(
            '/api/consent-assessment-status?user_id=1&user_id=2')
        self.assert200(rv)
        self.assertEquals(len(rv.json['status']), 1)
        self.assertEquals(
            rv.json['status'][0]['consents'][0]['assessment_status'],
            'Not Enrolled')
