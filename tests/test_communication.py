"""Unit test module for communication"""
from datetime import timedelta
from flask_webtest import SessionScope

from portal.database import db
from portal.models.audit import Audit
from portal.models.assessment_status import overall_assessment_status
from portal.models.communication import Communication
from portal.models.communication_request import CommunicationRequest
from portal.models.fhir import CC
from portal.models.identifier import Identifier
from portal.models.intervention import Intervention
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.role import ROLE
from portal.system_uri import ICHOM, TRUENTH_CR_NAME
from portal.tasks import update_patient_loop
from tests import TEST_USER_ID, TEST_USERNAME
from tests.test_assessment_status import TestQuestionnaireSetup, mock_qr
from tests.test_assessment_status import symptom_tracker_instruments


def mock_communication_request(
        questionnaire_bank_name,
        notify_post_qb_start,
        lr_uuid=None,
        communication_request_name=None,
        qb_iteration=None):
    qb = QuestionnaireBank.query.filter_by(name=questionnaire_bank_name).one()
    if lr_uuid is None:
        lr_uuid = "5424efca-9f24-7ff5-cb41-96c1f6546fab"
    cr = CommunicationRequest(
        status='active',
        questionnaire_bank=qb,
        notify_post_qb_start=notify_post_qb_start,
        lr_uuid=lr_uuid,
        qb_iteration=qb_iteration)
    if communication_request_name:
        ident = Identifier(
            system=TRUENTH_CR_NAME, value=communication_request_name)
        cr.identifiers.append(ident)
    with SessionScope(db):
        db.session.add(cr)
        db.session.commit()
    return db.session.merge(cr)


class TestCommunication(TestQuestionnaireSetup):
    # by inheriting from TestQuestionnaireSetup, pick up the
    # same mocking done for interacting with QuestionnaireBanks et al

    def test_empty(self):
        # Base test system shouldn't generate any messages
        count_b4 = Communication.query.count()
        self.assertFalse(count_b4)

        update_patient_loop(update_cache=False, queue_messages=True)
        count_after = Communication.query.count()
        self.assertEquals(count_b4, count_after)

    def test_nearready_message(self):
        # At 13 days with all work in-progress, shouldn't generate message

        mock_communication_request('localized', '{"days": 14}')

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(backdate=timedelta(days=13))
        self.promote_user(role_name=ROLE.PATIENT)
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='comorb',
                status='in-progress')

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertFalse(expected)

    def test_ready_message(self):
        # At 14 days with all work in-progress, should generate message

        mock_communication_request(
            'localized', '{"days": 14}',
            communication_request_name="Symptom Tracker | 3 Mo Reminder (1)")

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(backdate=timedelta(days=14))
        self.promote_user(role_name=ROLE.PATIENT)
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='comorb',
                status='in-progress')

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertEquals(expected.user_id, TEST_USER_ID)

    def test_noworkdone_message(self):
        # At 14 days with no work started, should generate message

        mock_communication_request('localized', '{"days": 14}')

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(backdate=timedelta(days=14))
        self.promote_user(role_name=ROLE.PATIENT)
        self.mark_localized()

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertEquals(expected.user_id, TEST_USER_ID)

    def test_done_message(self):
        # At 14 days with all work done, should not generate message

        mock_communication_request('localized', '{"days": 14}')

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(backdate=timedelta(days=14))
        self.promote_user(role_name=ROLE.PATIENT)
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26')
        mock_qr(user_id=TEST_USER_ID, instrument_id='comorb')

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertFalse(expected)

    def test_create_message(self):

        cr = mock_communication_request(
            'localized', '{"days": 14}',
            communication_request_name="Symptom Tracker | 3 Mo Reminder (1)")

        comm = Communication(user_id=TEST_USER_ID, communication_request=cr)

        # in testing, link_url isn't set:
        st = Intervention.query.filter_by(name='self_management').one()
        if not st.link_url:
            st.link_url = 'https://stg-sm.cirg.washington.edu'

        comm.generate_and_send()

        # Testing config doesn't send email unless MAIL_SUPPRESS_SEND
        # is set false.  Confirm persisted data from the fake send
        # looks good.

        self.assertTrue(comm.message)
        self.assertEquals(comm.message.recipients, TEST_USERNAME)
        self.assertEquals(comm.status, 'completed')


class TestCommunicationTnth(TestQuestionnaireSetup):
    # by inheriting from TestQuestionnaireSetup, pick up the
    # same mocking done for interacting with QuestionnaireBanks et al

    # set to pull in TrueNTH QBs:
    eproms_or_tnth = 'tnth'

    def test_early(self):
        # Prior to days passing, no message should be generated
        mock_communication_request('symptom_tracker', '{"days": 90}')

        self.promote_user(role_name=ROLE.PATIENT)
        self.login()
        self.add_required_clinical_data(backdate=timedelta(days=89))
        self.test_user = db.session.merge(self.test_user)

        # Confirm test user qualifies for ST QB
        self.assertTrue(
            QuestionnaireBank.qbs_for_user(self.test_user, 'baseline'))

        # Being a day short, shouldn't fire
        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertFalse(expected)

    def test_st_done(self):
        # Symptom Tracker QB with completed shouldn't fire
        mock_communication_request('symptom_tracker', '{"days": 90}')

        self.promote_user(role_name=ROLE.PATIENT)
        self.login()
        self.add_required_clinical_data(backdate=timedelta(days=91))
        self.test_user = db.session.merge(self.test_user)

        # Confirm test user qualifies for ST QB
        self.assertTrue(
            QuestionnaireBank.qbs_for_user(self.test_user, 'baseline'))

        for instrument in symptom_tracker_instruments:
            mock_qr(user_id=TEST_USER_ID, instrument_id=instrument)

        # With all q's done, shouldn't generate a message
        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertFalse(expected)

    def test_st_undone(self):
        # Symptom Tracker QB with incompleted should generate communication
        mock_communication_request('symptom_tracker', '{"days": 90}')

        self.promote_user(role_name=ROLE.PATIENT)
        self.login()
        self.add_required_clinical_data(backdate=timedelta(days=91))
        self.test_user = db.session.merge(self.test_user)

        # Confirm test user qualifies for ST QB
        self.assertTrue(
            QuestionnaireBank.qbs_for_user(self.test_user, 'baseline'))

        # With most q's undone, should generate a message
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26')
        self.assertEquals(
           'In Progress', overall_assessment_status(TEST_USER_ID))
        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertTrue(expected)

    def test_st_metastatic(self):
        # Symptom Tracker QB on metastatic patient shouldn't qualify
        mock_communication_request('symptom_tracker', '{"days": 90}')

        self.promote_user(role_name=ROLE.PATIENT)
        self.login()
        self.add_required_clinical_data(backdate=timedelta(days=91))
        self.test_user = db.session.merge(self.test_user)
        self.test_user.save_constrained_observation(
            codeable_concept=CC.PCaLocalized, value_quantity=CC.FALSE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID))

        # Confirm test user doesn't qualify for ST QB
        self.assertFalse(
            QuestionnaireBank.qbs_for_user(self.test_user, 'baseline'))

        # shouldn't generate a message either
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26')
        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertFalse(expected)

    def test_procedure_update(self):
        # Newer procedure should alter trigger date and suspend message
        mock_communication_request('symptom_tracker', '{"days": 90}')

        self.promote_user(role_name=ROLE.PATIENT)
        self.login()
        self.add_required_clinical_data(backdate=timedelta(days=91))
        self.test_user = db.session.merge(self.test_user)

        # Confirm test user qualifies for ST QB
        self.assertTrue(
            QuestionnaireBank.qbs_for_user(self.test_user, 'baseline'))

        # Add fresh procedure
        self.add_procedure('4', 'External beam radiation therapy', ICHOM)

        # New procedure date should suspend message
        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertFalse(expected)

    def test_persist(self):
        cr = mock_communication_request(
            questionnaire_bank_name='symptom_tracker_recurring',
            notify_post_qb_start='{days="30"}',
            communication_request_name='test-communication-request')

        serial = cr.as_fhir()
        self.assertEquals(serial['resourceType'], 'CommunicationRequest')
        copy = CommunicationRequest.from_fhir(serial)
        self.assertEquals(cr.questionnaire_bank.name,
                          copy.questionnaire_bank.name)
