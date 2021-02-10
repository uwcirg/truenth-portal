"""Module to test assessment_status"""

import copy
from datetime import datetime
from pytz import timezone, utc
from random import choice
from string import ascii_letters

from dateutil.relativedelta import relativedelta
from flask_webtest import SessionScope
import pytest
from sqlalchemy.orm.exc import NoResultFound

from portal.date_tools import FHIR_datetime, utcnow_sans_micro
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.clinical_constants import CC
from portal.models.encounter import Encounter
from portal.models.identifier import Identifier
from portal.models.intervention import INTERVENTION
from portal.models.organization import Organization
from portal.models.overall_status import OverallStatus
from portal.models.qb_status import QB_Status
from portal.models.qb_timeline import invalidate_users_QBT
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
    QuestionnaireBankQuestionnaire,
)
from portal.models.questionnaire_response import (
    QNR_results,
    QuestionnaireResponse,
    aggregate_responses,
    qnr_document_id,
)
from portal.models.recur import Recur
from portal.models.research_protocol import ResearchProtocol
from portal.models.role import ROLE
from portal.models.user import User
from portal.system_uri import ICHOM
from tests import TEST_USER_ID, TestCase, associative_backdate

now = utcnow_sans_micro()


def mock_qr(
        instrument_id, status='completed', timestamp=None, qb=None,
        doc_id=None, iteration=None, user_id=TEST_USER_ID, entry_method=None):
    if not doc_id:
        doc_id = ''.join(choice(ascii_letters) for _ in range(10))
    timestamp = timestamp or utcnow_sans_micro()
    qr_document = {
        "authored": FHIR_datetime.as_fhir(timestamp),
        "questionnaire": {
            "display": "Additional questions",
            "reference":
                "https://{}/api/questionnaires/{}".format(
                    'SERVER_NAME', instrument_id)},
        "identifier": {
            "use": "official",
            "label": "cPRO survey session ID",
            "value": doc_id,
            "system": "https://stg-ae.us.truenth.org/eproms-demo"}
    }

    # Strip TZ info if test happens to include
    if timestamp.tzinfo is not None:
        utc_time = timestamp.astimezone(utc)
        timestamp = utc_time.replace(tzinfo=None)
    enc = Encounter(
        status='planned', auth_method='url_authenticated', user_id=user_id,
        start_time=timestamp)
    if entry_method:
        enc.type.append(entry_method.codings[0])
    with SessionScope(db):
        db.session.add(enc)
        db.session.commit()
    enc = db.session.merge(enc)
    if not qb:
        qstats = QB_Status(
            User.query.get(user_id),
            research_study_id=0,
            as_of_date=timestamp)
        qbd = qstats.current_qbd()
        qb, iteration = qbd.questionnaire_bank, qbd.iteration

    qr = QuestionnaireResponse(
        subject_id=user_id,
        status=status,
        document=qr_document,
        encounter_id=enc.id,
        questionnaire_bank=qb,
        qb_iteration=iteration)
    with SessionScope(db):
        db.session.add(qr)
        db.session.commit()
    invalidate_users_QBT(user_id=user_id, research_study_id='all')


localized_instruments = {'eproms_add', 'epic26', 'comorb'}
metastatic_baseline_instruments = {
    'eortc', 'eproms_add', 'ironmisc', 'factfpsi', 'epic23', 'prems'}
metastatic_indefinite_instruments = {'irondemog'}
metastatic_3 = {
    'eortc', 'eproms_add', 'ironmisc'}
metastatic_4 = {
    'eortc', 'eproms_add', 'ironmisc', 'factfpsi'}
metastatic_6 = {
    'eortc', 'eproms_add', 'ironmisc', 'factfpsi', 'epic23', 'prems'}
symptom_tracker_instruments = {'epic26', 'eq5d', 'maxpc', 'pam'}


def mock_questionnairebanks(eproms_or_tnth):
    """Create a series of near real world questionnaire banks

    :param eproms_or_tnth: controls which set of questionnairebanks are
        generated.  As restrictions exist, such as two QBs with the same
        classification can't have the same instrument, it doesn't work to mix
        them.

    """
    if eproms_or_tnth == 'eproms':
        return mock_eproms_questionnairebanks()
    elif eproms_or_tnth == 'tnth':
        return mock_tnth_questionnairebanks()
    else:
        raise ValueError('expecting `eproms` or `tntn`, not `{}`'.format(
            eproms_or_tnth))


def mock_eproms_questionnairebanks():
    # Define base ResearchProtocols
    localized_protocol = ResearchProtocol(
        name='localized_protocol',
        research_study_id=0)
    metastatic_protocol = ResearchProtocol(
        name='metastatic_protocol',
        research_study_id=0)
    with SessionScope(db):
        db.session.add(localized_protocol)
        db.session.add(metastatic_protocol)
        db.session.commit()
    localized_protocol = db.session.merge(localized_protocol)
    metastatic_protocol = db.session.merge(metastatic_protocol)
    locpro_id = localized_protocol.id
    metapro_id = metastatic_protocol.id

    # Define test Orgs and QuestionnaireBanks for each group
    localized_org = Organization(name='localized')
    localized_org.research_protocols.append(localized_protocol)
    metastatic_org = Organization(name='metastatic')
    metastatic_org.research_protocols.append(metastatic_protocol)

    # from https://docs.google.com/spreadsheets/d/\
    # 1oJ8HKfMHOdXkSshjRlr8lFXxT4aUHX5ntxnKMgf50wE/edit#gid=1339608238
    three_q_recur = Recur(
        start='{"months": 3}', cycle_length='{"months": 6}',
        termination='{"months": 24}')
    four_q_recur = Recur(
        start='{"months": 6}', cycle_length='{"years": 1}',
        termination='{"months": 33}')
    six_q_recur = Recur(
        start='{"years": 1}', cycle_length='{"years": 1}',
        termination='{"years": 3, "months": 3}')

    for name in (localized_instruments.union(*(
            metastatic_baseline_instruments,
            metastatic_indefinite_instruments,
            metastatic_3,
            metastatic_4,
            metastatic_6))):
        TestCase.add_questionnaire(name=name)

    with SessionScope(db):
        db.session.add(localized_org)
        db.session.add(metastatic_org)
        db.session.add(three_q_recur)
        db.session.add(four_q_recur)
        db.session.add(six_q_recur)
        db.session.commit()
    localized_org, metastatic_org = map(
        db.session.merge, (localized_org, metastatic_org))
    three_q_recur = db.session.merge(three_q_recur)
    four_q_recur = db.session.merge(four_q_recur)
    six_q_recur = db.session.merge(six_q_recur)

    # Localized baseline
    l_qb = QuestionnaireBank(
        name='localized',
        classification='baseline',
        research_protocol_id=locpro_id,
        start='{"days": 0}',
        overdue='{"days": 7}',
        expired='{"months": 3}')
    for rank, instrument in enumerate(localized_instruments):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        l_qb.questionnaires.append(qbq)

    # Metastatic baseline
    mb_qb = QuestionnaireBank(
        name='metastatic',
        classification='baseline',
        research_protocol_id=metapro_id,
        start='{"days": 0}',
        overdue='{"days": 30}',
        expired='{"months": 3}')
    for rank, instrument in enumerate(metastatic_baseline_instruments):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        mb_qb.questionnaires.append(qbq)

    # Metastatic indefinite
    mi_qb = QuestionnaireBank(
        name='metastatic_indefinite',
        classification='indefinite',
        research_protocol_id=metapro_id,
        start='{"days": 0}',
        expired='{"years": 50}')
    for rank, instrument in enumerate(metastatic_indefinite_instruments):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        mi_qb.questionnaires.append(qbq)

    # Metastatic recurring 3
    mr3_qb = QuestionnaireBank(
        name='metastatic_recurring3',
        classification='recurring',
        research_protocol_id=metapro_id,
        start='{"days": 0}',
        overdue='{"days": 30}',
        expired='{"months": 3}',
        recurs=[three_q_recur])
    for rank, instrument in enumerate(metastatic_3):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        mr3_qb.questionnaires.append(qbq)

    # Metastatic recurring 4
    mr4_qb = QuestionnaireBank(
        name='metastatic_recurring4',
        classification='recurring',
        research_protocol_id=metapro_id,
        recurs=[four_q_recur],
        start='{"days": 0}',
        overdue='{"days": 30}',
        expired='{"months": 3}')
    for rank, instrument in enumerate(metastatic_4):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        mr4_qb.questionnaires.append(qbq)

    # Metastatic recurring 6
    mr6_qb = QuestionnaireBank(
        name='metastatic_recurring6',
        classification='recurring',
        research_protocol_id=metapro_id,
        recurs=[six_q_recur],
        start='{"days": 0}',
        overdue='{"days": 30}',
        expired='{"months": 3}')
    for rank, instrument in enumerate(metastatic_6):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        mr6_qb.questionnaires.append(qbq)

    with SessionScope(db):
        db.session.add(l_qb)
        db.session.add(mb_qb)
        db.session.add(mi_qb)
        db.session.add(mr3_qb)
        db.session.add(mr4_qb)
        db.session.add(mr6_qb)
        db.session.commit()


def mock_tnth_questionnairebanks():
    for name in (symptom_tracker_instruments):
        TestCase.add_questionnaire(name=name)

    # Symptom Tracker Baseline
    self_management = INTERVENTION.SELF_MANAGEMENT
    st_qb = QuestionnaireBank(
        name='symptom_tracker',
        classification='baseline',
        intervention_id=self_management.id,
        start='{"days": 0}',
        expired='{"months": 3}'
    )
    for rank, instrument in enumerate(symptom_tracker_instruments):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        st_qb.questionnaires.append(qbq)

    # Symptom Tracker Recurrence
    st_recur = Recur(
        start='{"months": 3}', cycle_length='{"months": 3}',
        termination='{"months": 27}')

    with SessionScope(db):
        db.session.add(st_qb)
        db.session.add(st_recur)
        db.session.commit()

    self_management = INTERVENTION.SELF_MANAGEMENT
    st_recur_qb = QuestionnaireBank(
        name='symptom_tracker_recurring',
        classification='recurring',
        intervention_id=self_management.id,
        start='{"days": 0}',
        expired='{"months": 3}',
        recurs=[st_recur]
    )
    for rank, instrument in enumerate(symptom_tracker_instruments):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        st_recur_qb.questionnaires.append(qbq)
    with SessionScope(db):
        db.session.add(st_recur_qb)
        db.session.commit()


class TestQuestionnaireSetup(TestCase):
    "Base for test classes needing mock questionnaire setup"

    eproms_or_tnth = 'eproms'  # modify in child class to test `tnth`

    def setUp(self):
        super(TestQuestionnaireSetup, self).setUp()
        mock_questionnairebanks(self.eproms_or_tnth)


class TestAggregateResponses(TestQuestionnaireSetup):

    @pytest.mark.skip("no longer raising on str vs datetime sort")
    def test_authored_sort(self):
        consent_date = datetime.strptime(
            "2021-01-25 23:43:38", "%Y-%m-%d %H:%M:%S")
        self.bless_with_basics(
            setdate=consent_date, local_metastatic='metastatic')
        instrument_id = 'eortc'
        d1 = timezone('Australia/Sydney').localize(
            consent_date + relativedelta(days=10, seconds=2))
        d2 = timezone('US/Eastern').localize(
            consent_date + relativedelta(days=10))

        # d1 and d2 sort differently depending on datetime or
        # lexicographical string sort:
        assert d1 < d2
        assert FHIR_datetime.as_fhir(d1) > FHIR_datetime.as_fhir(d2)

        for dt in (d1, d2):
            # each qr added forces a sort - confirm it raises due to tz
            mock_qr(instrument_id=instrument_id, timestamp=dt)

        # Confirm sort order by authored, regardless of timezone, etc.
        user = db.session.merge(self.test_user)
        qr = QNR_results(user=user, research_study_id=0)
        with pytest.raises(ValueError) as e:
            qr.qnrs
        assert "non UTC timezone" in str(e.value)

    def test_aggregate_response_timepoints(self):
        # generate a few mock qr's from various qb iterations, confirm
        # time points.

        nineback, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=9, hours=1))
        self.bless_with_basics(
            setdate=nineback, local_metastatic='metastatic')
        instrument_id = 'eortc'
        for months_back in (0, 3, 6, 9):
            backdate, _ = associative_backdate(
                now=now, backdate=relativedelta(months=months_back))
            mock_qr(instrument_id=instrument_id, timestamp=backdate)

        # add staff user w/ same org association for bundle creation

        staff = self.add_user(username='staff')
        staff.organizations.append(Organization.query.filter(
                Organization.name == 'metastatic').one())
        self.promote_user(staff, role_name=ROLE.STAFF.value)
        staff = db.session.merge(staff)
        bundle = aggregate_responses(
            instrument_ids=[instrument_id],
            research_study_id=0,
            current_user=staff)
        expected = {'Baseline', 'Month 3', 'Month 6', 'Month 9'}
        found = [i['timepoint'] for i in bundle['entry']]
        assert set(found) == expected

    def test_site_ids(self):
        # bless org w/ expected identifier type
        wanted_system = 'http://pcctc.org/'
        unwanted_system = 'http://other.org/'
        self.app.config['REPORTING_IDENTIFIER_SYSTEMS'] = [wanted_system]
        id_value = '146-11'
        org = Organization.query.filter(
            Organization.name == 'metastatic').one()
        id1 = Identifier(
            system=wanted_system, use='secondary', value=id_value)
        id2 = Identifier(
            system=unwanted_system, use='secondary', value=id_value)
        org.identifiers.append(id1)
        org.identifiers.append(id2)

        with SessionScope(db):
            db.session.commit()

        nineback, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=9, hours=1))
        self.bless_with_basics(
            setdate=nineback, local_metastatic='metastatic')
        instrument_id = 'eortc'
        mock_qr(instrument_id=instrument_id)

        # add staff user w/ same org association for bundle creation

        staff = self.add_user(username='staff')
        staff.organizations.append(Organization.query.filter(
                Organization.name == 'metastatic').one())
        self.promote_user(staff, role_name=ROLE.STAFF.value)
        staff = db.session.merge(staff)
        bundle = aggregate_responses(
            instrument_ids=[instrument_id],
            research_study_id=0,
            current_user=staff)
        id1 = db.session.merge(id1)
        assert 1 == len(bundle['entry'])
        assert (1 ==
                len(bundle['entry'][0]['subject']['careProvider']))
        assert (1 ==
                len(bundle['entry'][0]['subject']['careProvider'][0]
                    ['identifier']))
        assert (id1.as_fhir() ==
                bundle['entry'][0]['subject']['careProvider'][0]
                ['identifier'][0])


class TestQB_Status(TestQuestionnaireSetup):

    def test_qnr_id(self):
        qb = QuestionnaireBank.query.first()
        mock_qr(
            instrument_id='irondemog',
            status='in-progress', qb=qb,
            doc_id='two11')
        qb = db.session.merge(qb)
        result = qnr_document_id(
            subject_id=TEST_USER_ID,
            questionnaire_bank_id=qb.id,
            questionnaire_name='irondemog',
            iteration=None,
            status='in-progress')
        assert result == 'two11'

    def test_qnr_id_missing(self):
        qb = QuestionnaireBank.query.first()
        qb = db.session.merge(qb)
        with pytest.raises(NoResultFound):
            result = qnr_document_id(
                subject_id=TEST_USER_ID,
                questionnaire_bank_id=qb.id,
                questionnaire_name='irondemog',
                iteration=None,
                status='in-progress')

    def test_enrolled_in_metastatic(self):
        """metastatic should include baseline and indefinite"""
        self.bless_with_basics(local_metastatic='metastatic')
        user = db.session.merge(self.test_user)

        a_s = QB_Status(
            user=user,
            research_study_id=0,
            as_of_date=now)
        assert a_s.enrolled_in_classification('baseline')
        assert a_s.enrolled_in_classification('indefinite')

    def test_enrolled_in_localized(self):
        """localized should include baseline but not indefinite"""
        self.bless_with_basics(local_metastatic='localized')
        user = db.session.merge(self.test_user)

        a_s = QB_Status(
            user=user,
            research_study_id=0,
            as_of_date=now)
        assert a_s.enrolled_in_classification('baseline')
        assert not a_s.enrolled_in_classification('indefinite')

    def test_localized_using_org(self):
        self.bless_with_basics(local_metastatic='localized', setdate=now)
        self.test_user = db.session.merge(self.test_user)

        # confirm appropriate instruments
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=now)
        assert (set(a_s.instruments_needing_full_assessment()) ==
                localized_instruments)

    def test_localized_on_time(self):
        # User finished both on time
        self.bless_with_basics(local_metastatic='localized', setdate=now)
        mock_qr(instrument_id='eproms_add', timestamp=now)
        mock_qr(instrument_id='epic26', timestamp=now)
        mock_qr(instrument_id='comorb', timestamp=now)

        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=now)
        assert a_s.overall_status == OverallStatus.completed

        # confirm appropriate instruments
        assert not a_s.instruments_needing_full_assessment('all')

    def test_localized_inprogress_on_time(self):
        # User finished both on time
        self.bless_with_basics(local_metastatic='localized', setdate=now)
        mock_qr(
            instrument_id='eproms_add', status='in-progress',
            doc_id='eproms_add', timestamp=now)
        mock_qr(
            instrument_id='epic26', status='in-progress', doc_id='epic26',
            timestamp=now)
        mock_qr(
            instrument_id='comorb', status='in-progress', doc_id='comorb',
            timestamp=now)

        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=now)
        assert a_s.overall_status == OverallStatus.in_progress

        # confirm appropriate instruments
        assert not a_s.instruments_needing_full_assessment()
        assert set(a_s.instruments_in_progress()) == localized_instruments

    def test_localized_in_process(self):
        # User finished one, time remains for other
        self.bless_with_basics(local_metastatic='localized', setdate=now)
        mock_qr(instrument_id='eproms_add', timestamp=now)

        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=now)
        assert a_s.overall_status == OverallStatus.in_progress

        # confirm appropriate instruments
        assert (localized_instruments -
                set(a_s.instruments_needing_full_assessment('all')) ==
                {'eproms_add'})
        assert not a_s.instruments_in_progress()

    def test_metastatic_on_time(self):
        # User finished both on time

        self.bless_with_basics(
            local_metastatic='metastatic', setdate=now)
        for i in metastatic_baseline_instruments:
            mock_qr(instrument_id=i, timestamp=now)
        mi_qb = QuestionnaireBank.query.filter_by(
            name='metastatic_indefinite').first()
        mock_qr(instrument_id='irondemog', qb=mi_qb, timestamp=now)

        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=now)
        assert a_s.overall_status == OverallStatus.completed

        # shouldn't need full or any inprocess
        assert not a_s.instruments_needing_full_assessment('all')
        assert not a_s.instruments_in_progress('all')

    def test_metastatic_due(self):
        # hasn't taken, but still in OverallStatus.due period
        self.bless_with_basics(local_metastatic='metastatic', setdate=now)
        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=now)
        assert a_s.overall_status == OverallStatus.due

        # confirm list of expected intruments needing attention
        assert (metastatic_baseline_instruments ==
                set(a_s.instruments_needing_full_assessment()))
        assert not a_s.instruments_in_progress()

        # metastatic indefinite should also be 'due'
        assert (metastatic_indefinite_instruments ==
                set(a_s.instruments_needing_full_assessment('indefinite')))
        assert not a_s.instruments_in_progress('indefinite')

    def test_localized_overdue(self):
        # if the user completed something on time, and nothing else
        # is due, should see the thank you message.

        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=1))
        self.bless_with_basics(
            setdate=backdate, local_metastatic='localized')

        # backdate so the baseline q's have expired
        mock_qr(
            instrument_id='epic26', status='in-progress', timestamp=backdate)

        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=nowish)
        assert a_s.overall_status == OverallStatus.partially_completed

        # with all q's expired,
        # instruments_needing_full_assessment and instruments_in_progress
        # should be empty
        assert not a_s.instruments_needing_full_assessment()
        assert not a_s.instruments_in_progress()

    def test_localized_as_of_date(self):
        # backdating consent beyond expired and the status lookup date
        # within a valid window should show available assessments.

        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3))
        self.bless_with_basics(
            setdate=backdate, local_metastatic='localized')

        # backdate so the baseline q's have expired
        mock_qr(instrument_id='epic26', status='in-progress', doc_id='doc-26',
                timestamp=backdate)

        self.test_user = db.session.merge(self.test_user)
        as_of_date = backdate + relativedelta(days=2)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=as_of_date)
        assert a_s.overall_status == OverallStatus.in_progress

        # with only epic26 started, should see results for both
        # instruments_needing_full_assessment and instruments_in_progress
        assert ({'eproms_add', 'comorb'} ==
                set(a_s.instruments_needing_full_assessment()))
        assert ['doc-26'] == a_s.instruments_in_progress()

    def test_metastatic_as_of_date(self):
        # backdating consent beyond expired and the status lookup date
        # within a valid window should show available assessments.

        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3))
        self.bless_with_basics(setdate=backdate, local_metastatic='metastatic')

        # backdate so the baseline q's have expired
        mock_qr(instrument_id='epic23', status='in-progress', doc_id='doc-23',
                timestamp=backdate)

        self.test_user = db.session.merge(self.test_user)
        as_of_date = backdate + relativedelta(days=2)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=as_of_date)
        assert a_s.overall_status == OverallStatus.in_progress

        # with only epic26 started, should see results for both
        # instruments_needing_full_assessment and instruments_in_progress
        assert ['doc-23'] == a_s.instruments_in_progress()
        assert a_s.instruments_needing_full_assessment()

    def test_initial_recur_due(self):

        # backdate so baseline q's have expired, and we within the first
        # recurrence window
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=1))
        self.bless_with_basics(
            setdate=backdate, local_metastatic='metastatic')
        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=nowish)
        assert a_s.overall_status == OverallStatus.due

        # in the initial window w/ no questionnaires submitted
        # should include all from initial recur
        assert (set(a_s.instruments_needing_full_assessment()) ==
                metastatic_3)

        # confirm iteration 0
        assert a_s.current_qbd().iteration == 0

    def test_2nd_recur_due(self):

        # backdate so baseline q's have expired, and we within the 2nd
        # recurrence window
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=9, hours=1))
        self.bless_with_basics(
            setdate=backdate, local_metastatic='metastatic')
        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=nowish)
        assert a_s.overall_status == OverallStatus.due

        # in the initial window w/ no questionnaires submitted
        # should include all from initial recur
        assert set(a_s.instruments_needing_full_assessment()) == metastatic_3

        # however, we should be looking at iteration 2 (zero index)!
        assert a_s.current_qbd().iteration == 1

    def test_initial_recur_baseline_done(self):
        # backdate to be within the first recurrence window

        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, days=2))
        self.bless_with_basics(
            setdate=backdate, local_metastatic='metastatic')

        # add baseline QNRs, as if submitted nearly 3 months ago, during
        # baseline window
        backdated = nowish - relativedelta(months=2, days=25)
        baseline = QuestionnaireBank.query.filter_by(
            name='metastatic').one()
        for instrument in metastatic_baseline_instruments:
            mock_qr(instrument, qb=baseline, timestamp=backdated)

        self.test_user = db.session.merge(self.test_user)
        # Check status during baseline window
        a_s_baseline = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=backdated)
        assert a_s_baseline.overall_status == OverallStatus.completed
        assert not a_s_baseline.instruments_needing_full_assessment()

        # Whereas "current" status for the initial recurrence show due.
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=nowish)
        assert a_s.overall_status == OverallStatus.due

        # in the initial window w/ no questionnaires submitted
        # should include all from initial recur
        assert set(a_s.instruments_needing_full_assessment()) == metastatic_3

    def test_secondary_recur_due(self):

        # backdate so baseline q's have expired, and we are within the
        # second recurrence window
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=6, hours=1))
        self.bless_with_basics(
            setdate=backdate, local_metastatic='metastatic')
        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=nowish)
        assert a_s.overall_status == OverallStatus.due

        # w/ no questionnaires submitted
        # should include all from second recur
        assert set(a_s.instruments_needing_full_assessment()) == metastatic_4

    def test_none_org(self):
        # check users w/ none of the above org
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(Organization.query.get(0))
        self.login()
        self.bless_with_basics(
            local_metastatic='metastatic', setdate=now)
        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=now)
        assert a_s.overall_status == OverallStatus.due

    def test_boundary_overdue(self):
        self.login()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=-1))
        self.bless_with_basics(
            setdate=backdate, local_metastatic='localized')
        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=nowish)
        assert a_s.overall_status == OverallStatus.overdue

    def test_boundary_expired(self):
        "At expired, should be expired"
        self.login()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=1))
        self.bless_with_basics(
            setdate=backdate, local_metastatic='localized')
        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=nowish)
        assert a_s.overall_status == OverallStatus.expired

    def test_boundary_in_progress(self):
        self.login()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=-1))
        self.bless_with_basics(
            setdate=backdate, local_metastatic='localized')
        for instrument in localized_instruments:
            mock_qr(
                instrument_id=instrument, status='in-progress',
                timestamp=nowish)
        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=nowish)
        assert a_s.overall_status == OverallStatus.in_progress

    def test_boundary_recurring_in_progress(self):
        self.login()
        nowish = datetime.strptime(
            '2019-05-28 10:00:00', '%Y-%m-%d %H:%M:%S')
        backdate = nowish - relativedelta(months=6, hours=-1)
        self.bless_with_basics(
            setdate=backdate, local_metastatic='metastatic')
        mr3_qb = QuestionnaireBank.query.filter_by(
            name='metastatic_recurring3').first()

        for instrument in metastatic_3:
            mock_qr(
                instrument_id=instrument, status='in-progress',
                qb=mr3_qb, timestamp=nowish, iteration=0)
        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=nowish)
        assert a_s.overall_status == OverallStatus.in_progress

    def test_boundary_in_progress_expired(self):
        self.login()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=1))
        self.bless_with_basics(
            setdate=backdate, local_metastatic='localized')
        for instrument in localized_instruments:
            mock_qr(
                instrument_id=instrument, status='in-progress',
                timestamp=nowish-relativedelta(days=1))
        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=nowish)
        assert a_s.overall_status == OverallStatus.partially_completed

    def test_all_expired_old_tx(self):
        self.login()
        # backdate outside of baseline window (which uses consent date)
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=4, hours=1))
        self.bless_with_basics(
            setdate=backdate, local_metastatic='localized')

        # provide treatment date outside of all recurrences
        tx_date = datetime(2000, 3, 12, 0, 0, 00, 000000)
        self.add_procedure(code='7', display='Focal therapy',
                           system=ICHOM, setdate=tx_date)

        self.test_user = db.session.merge(self.test_user)
        a_s = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=nowish)
        assert a_s.overall_status == OverallStatus.expired


class TestTnthQB_Status(TestQuestionnaireSetup):
    """Tests with Tnth QuestionnaireBanks"""

    eproms_or_tnth = 'tnth'

    def test_no_start_date(self):
        # W/O a biopsy (i.e. event start date), no questionnaries
        self.promote_user(role_name=ROLE.PATIENT.value)
        # toggle default setup - set biopsy false for test user
        self.login()
        self.test_user = db.session.merge(self.test_user)
        self.test_user.save_observation(
            codeable_concept=CC.BIOPSY, value_quantity=CC.FALSE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
            status='final', issued=now)
        qstats = QB_Status(
            self.test_user, research_study_id=0, as_of_date=now)
        assert not qstats.current_qbd()
        assert not qstats.enrolled_in_classification("baseline")
