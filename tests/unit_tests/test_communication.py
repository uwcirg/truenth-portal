# -*- coding: utf-8 -*-
"""Unit test module for communication"""
from __future__ import unicode_literals  # isort:skip

from datetime import datetime

from dateutil.relativedelta import relativedelta
from flask_webtest import SessionScope
import pytest
import regex

from portal.database import db
from portal.models.assessment_status import overall_assessment_status
from portal.models.audit import Audit
from portal.models.clinical_constants import CC
from portal.models.communication import (
    Communication,
    DynamicDictLookup,
    load_template_args,
)
from portal.models.communication_request import CommunicationRequest
from portal.models.identifier import Identifier
from portal.models.intervention import Intervention
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.role import ROLE
from portal.models.user import NO_EMAIL_PREFIX
from portal.system_uri import ICHOM, TRUENTH_CR_NAME
from portal.tasks import update_patient_loop
from tests import TEST_USER_ID, TEST_USERNAME
from tests.unit_tests.test_assessment_status import (
    TestQuestionnaireSetup,
    mock_qr,
    symptom_tracker_instruments,
)


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

    def test_dd(self):
        def f():
            return 'zzz'

        dd = DynamicDictLookup()
        dd['a'] = f
        dd['b'] = 'bbb'
        assert dd['a'] == 'zzz'
        assert dd['b'] == 'bbb'
        target = 'a {a} and b {b}'.format(**dd)
        assert dd['a'] in target
        assert dd['b'] in target

    def test_dd_no_key(self):
        dd = DynamicDictLookup()
        with pytest.raises(KeyError):
            dd['a']

    def test_unicode(self):
        dd = DynamicDictLookup()
        dd['u'] = '✓'
        target = 'works {u}'
        result = target.format(**dd)
        assert '✓' in result

    def test_dd_no_extra_calls(self):
        def bad():
            raise ValueError("shouldn't call me")

        def good():
            return 'good results'

        dd = DynamicDictLookup()
        dd['bad'] = bad
        dd['good'] = good

        ok = "string with just the {good} reference"
        # format forces __get_item__ on all key/values by default
        with pytest.raises(ValueError):
            ok.format(**dd)

        # using minimal_subdict, should fly
        assert 'good results' in ok.format(**dd.minimal_subdict(ok))

    def test_template_org(self):
        self.bless_with_basics()
        user = db.session.merge(self.test_user)
        dd = load_template_args(user=user, questionnaire_bank_id=None)
        assert dd['parent_org'] == '101'
        assert dd['clinic_name'] == '1001'

    def test_pw_button(self):
        dd = load_template_args(user=None, questionnaire_bank_id=None)
        assert 'forgot-password' in dd['password_reset_button']

    def test_st_button(self):
        dd = load_template_args(user=None, questionnaire_bank_id=None)
        assert 'Symptom Tracker' in dd['st_button']

    def test_due_date(self):
        qb = QuestionnaireBank.query.filter_by(name='localized').one()
        qb_id = qb.id

        # with no timezone
        dt = datetime(2017, 6, 10, 20, 00, 00, 000000)
        self.bless_with_basics(setdate=dt)
        self.promote_user(role_name=ROLE.PATIENT.value)
        user = db.session.merge(self.test_user)

        dd = load_template_args(user=user, questionnaire_bank_id=qb_id)
        assert dd['questionnaire_due_date'] == '10 Jun 2017'

        # with timezone where (day = UTCday + 1)
        user.timezone = "Asia/Tokyo"
        with SessionScope(db):
            db.session.add(user)
            db.session.commit()
        user = db.session.merge(user)

        dd = load_template_args(user=user, questionnaire_bank_id=qb_id)
        assert dd['questionnaire_due_date'] == '11 Jun 2017'

        # with calculated_due
        qb.due = "{\"days\": 7}"
        with SessionScope(db):
            db.session.add(qb)
            db.session.commit()
        user = db.session.merge(user)

        dd = load_template_args(user=user, questionnaire_bank_id=qb_id)
        assert dd['questionnaire_due_date'] == '18 Jun 2017'

    def test_empty(self):
        # Base test system shouldn't generate any messages
        count_b4 = Communication.query.count()
        assert not count_b4

        update_patient_loop(update_cache=False, queue_messages=True)
        count_after = Communication.query.count()
        assert count_b4 == count_after

    def test_nearready_message(self):
        # At 13 days with all work in-progress, shouldn't generate message

        mock_communication_request('localized', '{"days": 14}')

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(
            backdate=relativedelta(days=13), local_metastatic='localized')
        self.promote_user(role_name=ROLE.PATIENT.value)
        mock_qr(instrument_id='eproms_add', status='in-progress')
        mock_qr(instrument_id='epic26', status='in-progress')
        mock_qr(instrument_id='comorb', status='in-progress')

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        assert not expected

    def test_ready_message(self):
        # At 14 days with all work in-progress, should generate message

        mock_communication_request(
            'localized', '{"days": 14}',
            communication_request_name="Symptom Tracker | 3 Mo Reminder (1)")

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(
            backdate=relativedelta(days=14), local_metastatic='localized')
        self.promote_user(role_name=ROLE.PATIENT.value)
        mock_qr(instrument_id='eproms_add', status='in-progress')
        mock_qr(instrument_id='epic26', status='in-progress')
        mock_qr(instrument_id='comorb', status='in-progress')

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        assert expected.user_id == TEST_USER_ID

    def test_noworkdone_message(self):
        # At 14 days with no work started, should generate message

        mock_communication_request('localized', '{"days": 14}')

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(
            backdate=relativedelta(days=14), local_metastatic='localized')
        self.promote_user(role_name=ROLE.PATIENT.value)

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        assert expected.user_id == TEST_USER_ID

    def test_single_message(self):
        # With multiple time spaced CRs, only latest should send

        mock_communication_request('localized', '{"days": 7}')
        mock_communication_request('localized', '{"days": 14}')
        mock_communication_request('localized', '{"days": 21}')

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(
            backdate=relativedelta(days=22), local_metastatic='localized')
        self.promote_user(role_name=ROLE.PATIENT.value)

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query
        assert expected.count() == 3
        assert len([e for e in expected if e.status == 'preparation']) == 1
        assert len([e for e in expected if e.status == 'suspended']) == 2

    def test_no_email(self):
        # User w/o email shouldn't trigger communication

        mock_communication_request('localized', '{"days": 14}')

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(
            backdate=relativedelta(days=22), local_metastatic='localized')
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.test_user = db.session.merge(self.test_user)
        self.test_user.email = NO_EMAIL_PREFIX
        with SessionScope(db):
            db.session.commit()

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query
        assert expected.count() == 0

    def test_done_message(self):
        # At 14 days with all work done, should not generate message

        mock_communication_request('localized', '{"days": 14}')

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(
            backdate=relativedelta(days=14), local_metastatic='localized')
        self.promote_user(role_name=ROLE.PATIENT.value)
        mock_qr(instrument_id='eproms_add')
        mock_qr(instrument_id='epic26')
        mock_qr(instrument_id='comorb')

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        assert not expected

    def test_create_message(self):
        self.add_user('__system__')
        self.bless_with_basics()
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

        assert comm.message
        assert comm.message.recipients == TEST_USERNAME
        assert comm.status == 'completed'

    def test_preview(self):
        self.bless_with_basics()
        cr = mock_communication_request(
            'localized', '{"days": 14}',
            communication_request_name="Symptom Tracker | 3 Mo Reminder (1)")

        comm = Communication(user_id=TEST_USER_ID, communication_request=cr)

        # in testing, link_url isn't set:
        st = Intervention.query.filter_by(name='self_management').one()
        if not st.link_url:
            st.link_url = 'https://stg-sm.cirg.washington.edu'

        preview = comm.preview()

        assert '<style>' in preview.body
        assert preview.subject
        assert preview.recipients == TEST_USERNAME

    def test_practitioner(self):
        self.bless_with_basics()
        dr = self.add_practitioner(first_name='Bob', last_name='Jones')
        with SessionScope(db):
            db.session.add(dr)
            db.session.commit()
        dr, user = map(db.session.merge, (dr, self.test_user))
        user.practitioner_id = dr.id

        dd = load_template_args(user=user)
        assert dd['practitioner_name'] == 'Bob Jones'

    def test_missing_practitioner(self):
        self.bless_with_basics()
        user = db.session.merge(self.test_user)
        dd = load_template_args(user=user)
        assert dd['practitioner_name'] == ''

    def test_decision_support(self):
        self.bless_with_basics()
        self.add_system_user()
        user = db.session.merge(self.test_user)
        dd = load_template_args(user=user)

        # expecting a URL of form <host>/access/token/decision_support
        match = regex.match(
            r'<a href=(.*)/access/(.*)/decision_support(.*)',
            dd['decision_support_via_access_link'])
        assert match


class TestCommunicationTnth(TestQuestionnaireSetup):
    # by inheriting from TestQuestionnaireSetup, pick up the
    # same mocking done for interacting with QuestionnaireBanks et al

    # set to pull in TrueNTH QBs:
    eproms_or_tnth = 'tnth'

    def test_early(self):
        # Prior to days passing, no message should be generated
        mock_communication_request('symptom_tracker', '{"days": 90}')

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        self.add_required_clinical_data(backdate=relativedelta(days=89))
        self.test_user = db.session.merge(self.test_user)

        # Confirm test user qualifies for ST QB
        assert QuestionnaireBank.qbs_for_user(
            self.test_user, 'baseline', as_of_date=datetime.utcnow())

        # Being a day short, shouldn't fire
        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        assert not expected

    def test_st_done(self):
        # Symptom Tracker QB with completed shouldn't fire
        mock_communication_request('symptom_tracker', '{"days": 90}')

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        self.add_required_clinical_data(backdate=relativedelta(days=91))
        self.test_user = db.session.merge(self.test_user)

        # Confirm test user qualifies for ST QB
        assert QuestionnaireBank.qbs_for_user(
            self.test_user, 'baseline', as_of_date=datetime.utcnow())

        for instrument in symptom_tracker_instruments:
            mock_qr(instrument_id=instrument)

        # With all q's done, shouldn't generate a message
        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        assert not expected

    def test_st_undone(self):
        # Symptom Tracker QB with incompleted should generate communication
        mock_communication_request('symptom_tracker', '{"days": 30}')

        self.app.config['NO_CHALLENGE_WO_DATA'] = False
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        self.add_required_clinical_data(backdate=relativedelta(days=31))
        self.test_user = db.session.merge(self.test_user)
        self.test_user.birthdate = '1969-07-16'

        # Confirm test user qualifies for ST QB
        assert QuestionnaireBank.qbs_for_user(
            self.test_user, 'baseline', as_of_date=datetime.utcnow())

        # With most q's undone, should generate a message
        mock_qr(instrument_id='epic26')
        a_s, _ = overall_assessment_status(TEST_USER_ID)
        assert 'In Progress' == a_s
        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        assert expected

    def test_st_metastatic(self):
        # Symptom Tracker QB on metastatic patient shouldn't qualify
        mock_communication_request('symptom_tracker', '{"days": 90}')

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        self.add_required_clinical_data(backdate=relativedelta(days=91))
        self.test_user = db.session.merge(self.test_user)
        self.test_user.save_observation(
            codeable_concept=CC.PCaLocalized, value_quantity=CC.FALSE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
            status='final', issued=None)

        # Confirm test user doesn't qualify for ST QB
        assert not QuestionnaireBank.qbs_for_user(
            self.test_user, 'baseline', as_of_date=datetime.utcnow())

        # shouldn't generate a message either
        mock_qr(instrument_id='epic26')
        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        assert not expected

    def test_procedure_update(self):
        # Newer procedure should alter trigger date and suspend message
        mock_communication_request('symptom_tracker', '{"days": 90}')

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        self.add_required_clinical_data(backdate=relativedelta(days=91))
        self.test_user = db.session.merge(self.test_user)

        # Confirm test user qualifies for ST QB
        assert QuestionnaireBank.qbs_for_user(
            self.test_user, 'baseline', as_of_date=datetime.utcnow())

        # Add fresh procedure
        self.add_procedure('4', 'External beam radiation therapy', ICHOM)

        # New procedure date should suspend message
        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        assert not expected

    def test_persist(self):
        cr = mock_communication_request(
            questionnaire_bank_name='symptom_tracker_recurring',
            notify_post_qb_start='{"days": 30}',
            communication_request_name='test-communication-request')

        serial = cr.as_fhir()
        assert serial['resourceType'] == 'CommunicationRequest'
        copy = CommunicationRequest.from_fhir(serial)
        assert cr.questionnaire_bank.name == copy.questionnaire_bank.name
