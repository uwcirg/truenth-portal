"""Unit test module for questionnaire_bank"""

from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from flask_webtest import SessionScope
import pytest

from portal.date_tools import utcnow_sans_micro
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.identifier import Identifier
from portal.models.organization import (
    Organization,
    OrganizationResearchProtocol,
)
from portal.models.overall_status import OverallStatus
from portal.models.qb_status import QB_Status
from portal.models.qb_timeline import invalidate_users_QBT
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
    QuestionnaireBankQuestionnaire,
    trigger_date,
    visit_name,
)
from portal.models.recur import Recur
from portal.models.research_protocol import ResearchProtocol
from portal.models.role import ROLE
from portal.models.user_consent import UserConsent
from portal.system_uri import TRUENTH_QUESTIONNAIRE_CODE_SYSTEM
from tests import TEST_USER_ID, TestCase, associative_backdate
from tests.test_assessment_status import mock_qr

now = utcnow_sans_micro()


class TestQuestionnaireBankFixture(TestCase):
    """Fixture class for many QB test classes.

    Sets up what should be done via py.test fixtures, at this time used
    as an inherited unittest class by several QB test classes.

    NB, this class should NOT define any actual tests, or they will
    get redundantly run by each inheriting class!

    """

    @staticmethod
    def setup_org_n_rp(
            org=None, org_name='org', rp_name='proto',
            retired_as_of=None):
        """Create simple test org with RP, return (org, rp, rp_id)"""
        if not org:
            org = Organization(name=org_name)

        # RP may have already been setup - confirm
        # it's assigned to given org and return
        existing_rp = ResearchProtocol.query.filter(
            ResearchProtocol.name == rp_name).first()
        if existing_rp:
            if existing_rp not in org.research_protocols:
                org.research_protocols.append(existing_rp)
            return org, existing_rp, existing_rp.id

        rp = ResearchProtocol(name=rp_name, research_study_id=0)
        with SessionScope(db):
            db.session.add(org)
            db.session.add(rp)
            db.session.commit()
        org, rp = map(db.session.merge, (org, rp))
        if not retired_as_of:
            org.research_protocols.append(rp)
        else:
            o_rp = OrganizationResearchProtocol(
                research_protocol=rp, organization=org,
                retired_as_of=retired_as_of)
            with SessionScope(db):
                db.session.add(o_rp)
                db.session.commit()
            org, rp = map(db.session.merge, (org, rp))
        return (org, rp, rp.id)

    def setup_qb(
            self, questionnaire_name, qb_name, classification, rp_id,
            expired=None):
        """Shortcut to setup a testing QB with given values

        Sets up a single qb with a single questionnaire for given
        classification and research_protocol

        """
        if expired is None:
            expired = '{"days": 90}'
        qn = self.add_questionnaire(questionnaire_name)
        qb = QuestionnaireBank(
            name=qb_name,
            classification=classification,
            research_protocol_id=rp_id,
            start='{"days": 0}',
            expired=expired)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=qn, rank=0)
        qb.questionnaires.append(qbq)
        with SessionScope(db):
            db.session.add(qb)
            db.session.commit()
        return db.session.merge(qb)

    def setup_org_qbs(
            self, org=None, rp_name='v2', retired_as_of=None,
            include_indef=False):
        org_name = org.name if org else 'CRV'
        org, rp, rp_id = self.setup_org_n_rp(
            org=org, org_name=org_name, rp_name=rp_name,
            retired_as_of=retired_as_of)
        # enable re-entrance - if first q exists, probably a second
        # org is being setup - return as the rest is done
        q_name = 'eortc_{}'.format(rp_name)
        for q in Questionnaire.query.all():
            if q.name == q_name:
                return

        eortc = self.add_questionnaire(name=q_name)
        epic26 = self.add_questionnaire(name='epic26_{}'.format(rp_name))
        recur3 = Recur(
            start='{"months": 3}', cycle_length='{"months": 6}',
            termination='{"months": 24}')
        if rp_name == 'v5':
            recur3.start = '{"months": 2}'
        exists = Recur.query.filter_by(
            start=recur3.start, cycle_length=recur3.cycle_length,
            termination=recur3.termination).first()
        if exists:
            recur3 = exists

        recur6 = Recur(
            start='{"months": 6}', cycle_length='{"years": 1}',
            termination='{"years": 3, "months": 3}')
        if rp_name == 'v5':
            recur6.start = '{"months": 5}'
        exists = Recur.query.filter_by(
            start=recur6.start, cycle_length=recur6.cycle_length,
            termination=recur6.termination).first()
        if exists:
            recur6 = exists

        with SessionScope(db):
            db.session.add(eortc)
            db.session.add(epic26)
            db.session.add(recur3)
            db.session.add(recur6)
            db.session.commit()
        org, eortc, epic26, recur3, recur6 = map(
            db.session.merge, (org, eortc, epic26, recur3, recur6))

        qb_base = QuestionnaireBank(
            name='{} Baseline {}'.format(org_name, rp_name),
            classification='baseline',
            research_protocol_id=rp_id,
            start='{"days": 0}',
            overdue='{"days": 30}',
            expired='{"months": 3}')
        qbq = QuestionnaireBankQuestionnaire(questionnaire=epic26, rank=0)
        qbq2 = QuestionnaireBankQuestionnaire(questionnaire=eortc, rank=1)
        qb_base.questionnaires.append(qbq)
        qb_base.questionnaires.append(qbq2)

        qb_m3 = QuestionnaireBank(
            name='{}_recurring_3mo_period {}'.format(org_name, rp_name),
            classification='recurring',
            research_protocol_id=rp_id,
            start='{"days": 0}',
            overdue='{"days": 30}',
            expired='{"months": 3}',
            recurs=[recur3])
        qbq = QuestionnaireBankQuestionnaire(questionnaire=epic26, rank=0)
        qbq2 = QuestionnaireBankQuestionnaire(questionnaire=eortc, rank=1)
        qb_m3.questionnaires.append(qbq)
        qb_m3.questionnaires.append(qbq2)

        qb_m6 = QuestionnaireBank(
            name='{}_recurring_6mo_period {}'.format(org_name, rp_name),
            classification='recurring',
            research_protocol_id=rp_id,
            start='{"days": 0}',
            overdue='{"days": 30}',
            expired='{"months": 3}',
            recurs=[recur6])
        qbq = QuestionnaireBankQuestionnaire(questionnaire=epic26, rank=0)
        qbq2 = QuestionnaireBankQuestionnaire(questionnaire=eortc, rank=1)
        qb_m6.questionnaires.append(qbq)
        qb_m6.questionnaires.append(qbq2)

        with SessionScope(db):
            db.session.add(qb_base)
            db.session.add(qb_m3)
            db.session.add(qb_m6)
            db.session.commit()

        if include_indef:
            self.setup_qb(
                questionnaire_name='irondemog_{}'.format(rp_name),
                qb_name='indef_{}'.format(rp_name),
                classification='indefinite', rp_id=rp_id,
                expired="{\"years\": 50}")

        return db.session.merge(org)


class TestQuestionnaireBank(TestQuestionnaireBankFixture):

    def test_display_name(self):
        self.setup_org_qbs()
        qbs = QuestionnaireBank.query.all()
        expected = {
            'None Of The Above',
            'Crv Baseline V2',
            'Crv Recurring 3Mo Period V2',
            'Crv Recurring 6Mo Period V2'}
        assert expected == {q.display_name for q in qbs}

    def test_org_trigger_date(self):
        # testing org-based QBs
        org, rp, rp_id = self.setup_org_n_rp()
        q = self.add_questionnaire(name='q')
        q, org, self.test_user = map(db.session.merge,
                                     (q, org, self.test_user))
        qb = QuestionnaireBank(
            name='qb', research_protocol_id=rp_id, classification='baseline',
            start='{"days": 1}', expired='{"days": 2}')
        qbq = QuestionnaireBankQuestionnaire(rank=0, questionnaire=q)
        qb.questionnaires.append(qbq)

        # user without consents should return None
        assert not trigger_date(self.test_user, research_study_id=0)

        # user with consent should return consent date
        self.consent_with_org(org.id, setdate=now)
        self.test_user = db.session.merge(self.test_user)
        assert trigger_date(self.test_user, research_study_id=0) == now
        assert trigger_date(self.test_user, research_study_id=0, qb=qb) == now

    def test_start(self):
        org, rp, rp_id = self.setup_org_n_rp()
        q = self.add_questionnaire('q')
        q, org = map(db.session.merge, (q, org))
        qb = QuestionnaireBank(
            name='qb', research_protocol_id=rp_id, classification='baseline',
            start='{"days": 1}', expired='{"days": 2}')
        qbq = QuestionnaireBankQuestionnaire(rank=0, questionnaire=q)
        qb.questionnaires.append(qbq)

        trigger_date = datetime.strptime('2000-01-01', '%Y-%m-%d')
        start = qb.calculated_start(trigger_date).relative_start
        assert start > trigger_date
        assert start == datetime.strptime('2000-01-02', '%Y-%m-%d')

        end = qb.calculated_expiry(start)
        expected_expiry = datetime.strptime('2000-01-04', '%Y-%m-%d')
        assert end == expected_expiry

    def test_due(self):
        org, rp, rp_id = self.setup_org_n_rp()
        q = self.add_questionnaire('q')
        q, org = map(db.session.merge, (q, org))
        qb = QuestionnaireBank(
            name='qb', research_protocol_id=rp_id, classification='baseline',
            start='{"days": 1}', due='{"days": 2}')
        qbq = QuestionnaireBankQuestionnaire(rank=0, questionnaire=q)
        qb.questionnaires.append(qbq)

        trigger_date = datetime.strptime('2000-01-01', '%Y-%m-%d')
        now = datetime.now()
        start = qb.calculated_start(trigger_date).relative_start
        assert start > trigger_date
        assert start == datetime.strptime('2000-01-02', '%Y-%m-%d')

        due = qb.calculated_due(start)
        expected_due = datetime.strptime('2000-01-04', '%Y-%m-%d')
        assert due == expected_due

    def test_recurring_starts(self):
        # should get full list of QBDs for recurring qb
        self.setup_org_qbs()
        td = datetime.utcnow().replace(month=1, day=1)

        sixMoQB = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == 'CRV_recurring_6mo_period v2').one()
        results = sixMoQB.recurring_starts(trigger_date=td)
        # Expect in order, 6mo, 18mo, 30mo
        expect6 = next(results)
        assert visit_name(expect6) == 'Month 6'
        expect18 = next(results)
        assert visit_name(expect18) == 'Month 18'
        expect30 = next(results)
        assert visit_name(expect30) == 'Month 30'
        with pytest.raises(StopIteration):
            next(results)

    def test_questionnaire_serialize(self):
        q1 = self.add_questionnaire(name='q1')
        data = q1.as_fhir()
        assert data['resourceType'] == "Questionnaire"
        expected = Identifier(
            system=TRUENTH_QUESTIONNAIRE_CODE_SYSTEM, value='q1')
        assert Identifier.from_fhir(data['identifier'][0]) == expected

    def test_serialize(self):
        org, rp, rp_id = self.setup_org_n_rp()
        q1 = self.add_questionnaire(name='q1')
        q2 = self.add_questionnaire(name='q2')
        q1, q2, org = map(db.session.merge, (q1, q2, org))
        qb = QuestionnaireBank(
            name='qb', research_protocol_id=rp_id, classification='baseline',
            start='{"days": 0}', overdue='{"days": 5}', expired='{"days": 30}')
        for rank, q in enumerate((q1, q2)):
            qbq = QuestionnaireBankQuestionnaire(
                rank=rank,
                questionnaire=q)
            qb.questionnaires.append(qbq)
        with SessionScope(db):
            db.session.add(qb)
            db.session.commit()
        qb = db.session.merge(qb)

        data = qb.as_json()
        assert 'QuestionnaireBank' == data.get('resourceType')
        assert len(data['questionnaires']) == 2

    def test_import(self):
        org, rp, rp_id = self.setup_org_n_rp()
        rp_name = rp.name
        q1 = self.add_questionnaire(name='q1')
        q2 = self.add_questionnaire(name='q2')
        org, q1, q2 = map(db.session.merge, (org, q1, q2))

        data = {
            'resourceType': 'QuestionnaireBank',
            'research_protocol': {'reference': ('api/research_protocol/'
                                                '{}').format(rp_name)},
            'start': '{"days": 0}',
            'overdue': '{"weeks": 1}',
            'expired': '{"days": 30}',
            'questionnaires': [
                {
                    'rank': 2,
                    'questionnaire': {
                        'reference': 'api/questionnaire/{}?system={}'.format(
                            q1.name, TRUENTH_QUESTIONNAIRE_CODE_SYSTEM)}
                },
                {
                    'rank': 1,
                    'questionnaire': {
                        'reference': 'api/questionnaire/{}?system={}'.format(
                            q2.name, TRUENTH_QUESTIONNAIRE_CODE_SYSTEM)}
                }
            ],
            'id': 1,
            'name': 'bank',
            'classification': 'baseline'
        }
        qb = QuestionnaireBank.from_json(data)
        assert len(qb.questionnaires) == 2
        assert qb.research_protocol_id == rp_id
        assert qb.research_study_id == 0

    def test_lookup_for_user(self):
        crv, rp, rp_id = self.setup_org_n_rp(org_name='CRV')
        epic26 = self.add_questionnaire(name='epic26')
        eproms_add = self.add_questionnaire(name='eproms_add')
        comorb = self.add_questionnaire(name='comorb')
        crv, epic26, eproms_add, comorb = map(
            db.session.merge, (crv, epic26, eproms_add, comorb))

        bank = QuestionnaireBank(
            name='CRV', research_protocol_id=rp_id,
            start='{"days": 7}',
            expired='{"days": 90}')
        for rank, q in enumerate((epic26, eproms_add, comorb)):
            qbq = QuestionnaireBankQuestionnaire(
                questionnaire_id=q.id,
                rank=rank)
            bank.questionnaires.append(qbq)

        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)
        self.consent_with_org(org_id=crv.id, setdate=now)
        self.promote_user(role_name=ROLE.PATIENT.value)
        with SessionScope(db):
            db.session.add(bank)
            db.session.commit()

        # User associated with CRV org should generate appropriate
        # questionnaires
        self.test_user = db.session.merge(self.test_user)

        # Doesn't start for 7 days, initially shouldn't get any
        qb_stat = QB_Status(
            user=self.test_user, research_study_id=0, as_of_date=now)
        assert qb_stat.current_qbd() is None

        qb_stat = QB_Status(
            user=self.test_user,
            research_study_id=0,
            as_of_date=now + relativedelta(days=7))
        qb = qb_stat.current_qbd().questionnaire_bank
        results = list(qb.questionnaires)
        assert len(results) == 3
        # confirm rank sticks
        assert results[0].name == 'epic26'
        assert results[2].name == 'comorb'

    def test_questionnaire_gets(self):
        crv, rp, rp_id = self.setup_org_n_rp(org_name='CRV')
        epic26 = self.add_questionnaire(name='epic26')
        eproms_add = self.add_questionnaire(name='eproms_add')
        comorb = self.add_questionnaire(name='comorb')
        crv, epic26, eproms_add, comorb = map(
            db.session.merge, (crv, epic26, eproms_add, comorb))

        resp = self.client.get('/api/questionnaire')
        assert resp.status_code == 200
        assert len(resp.json['entry']) == 3
        assert all(('resource' in entry for entry in resp.json['entry']))

        resp = self.client.get('/api/questionnaire/{}?system={}'.format(
            'epic26', TRUENTH_QUESTIONNAIRE_CODE_SYSTEM))
        assert resp.status_code == 200
        q_ids = [
            ident for ident in resp.json['identifier'] if
            ident['system'] == TRUENTH_QUESTIONNAIRE_CODE_SYSTEM]
        assert len(q_ids) == 1
        assert q_ids[0]['value'] == 'epic26'

        bank = QuestionnaireBank(name='CRV', research_protocol_id=rp_id,
                                 start='{"days": 7}',
                                 expired='{"days": 90}')
        for rank, q in enumerate((epic26, eproms_add, comorb)):
            qbq = QuestionnaireBankQuestionnaire(
                questionnaire_id=q.id,
                rank=rank)
            bank.questionnaires.append(qbq)

        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)
        with SessionScope(db):
            db.session.add(bank)
            db.session.commit()

        resp = self.client.get('/api/questionnaire_bank')
        assert resp.status_code == 200
        assert resp.json['entry'][0]['resource']['name'] == 'none of the above'
        assert resp.json['entry'][1]['resource']['name'] == 'CRV'
        assert len(resp.json['entry'][1]['resource']['questionnaires']) == 3

    def test_visit_baseline(self):
        crv = self.setup_org_qbs()
        self.bless_with_basics(setdate=now)  # pick up a consent, etc.
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)

        qstats = QB_Status(self.test_user, 0, now)
        qbd = qstats.current_qbd()
        assert visit_name(qbd) == "Baseline"

    def test_visit_3mo(self):
        crv = self.setup_org_qbs()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3))
        self.bless_with_basics(setdate=backdate)
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)

        qstats = QB_Status(
            self.test_user,
            research_study_id=0,
            as_of_date=nowish+timedelta(hours=1))
        qbd = qstats.current_qbd()
        assert visit_name(qbd) == "Month 3"

        qbd.iteration = 1
        assert visit_name(qbd) == "Month 9"

    def test_visit_6mo(self):
        crv = self.setup_org_qbs()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=6))
        self.bless_with_basics(setdate=backdate)
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)

        qstats = QB_Status(
            self.test_user,
            research_study_id=0,
            as_of_date=nowish + timedelta(hours=1))
        qbd = qstats.current_qbd()
        assert visit_name(qbd) == "Month 6"

        qbd.iteration = 1
        assert visit_name(qbd) == "Month 18"

    def test_visit_9mo(self):
        crv = self.setup_org_qbs()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=9))
        self.bless_with_basics(setdate=backdate)
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)

        qstats = QB_Status(self.test_user, 0, nowish + timedelta(hours=1))
        qbd = qstats.current_qbd()
        assert visit_name(qbd) == "Month 9"

    def test_user_current_qb(self):
        crv = self.setup_org_qbs()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3))
        self.bless_with_basics(setdate=backdate)
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)

        self.login()
        resp = self.client.get('/api/user/{}/'
                               'questionnaire_bank'.format(TEST_USER_ID))
        assert resp.status_code == 200
        assert (resp.json['questionnaire_bank']['name']
                == 'CRV_recurring_3mo_period v2')

        dt = (nowish - relativedelta(months=2)).strftime('%Y-%m-%d')
        resp2 = self.client.get('/api/user/{}/questionnaire_bank?as_of_date='
                                '{}'.format(TEST_USER_ID, dt))
        assert resp2.status_code == 200
        assert (resp2.json['questionnaire_bank']['name']
                == 'CRV Baseline v2')

        # User's trigger was only 3 months ago.  At 4 months should
        # return a valid empty
        dt = (nowish - relativedelta(months=4)).strftime('%Y-%m-%d')
        resp3 = self.client.get('/api/user/{}/questionnaire_bank?as_of_date='
                                '{}'.format(TEST_USER_ID, dt))
        assert resp3.status_code == 200
        assert not resp3.json['questionnaire_bank']

    def test_outdated_inprogress_qb(self):
        # create base QB/RP
        org, rp, rp_id = self.setup_org_n_rp(org_name='testorg')
        qn = self.add_questionnaire(name='epic26')
        qn, org, self.test_user = map(
            db.session.merge, (qn, org, self.test_user))
        org_id = org.id
        qb = QuestionnaireBank(
            name='Test Questionnaire Bank',
            classification='baseline',
            research_protocol_id=rp_id,
            start='{"days": 0}',
            overdue='{"days": 7}',
            expired='{"days": 90}')
        qbq = QuestionnaireBankQuestionnaire(questionnaire=qn, rank=0)
        qb.questionnaires.append(qbq)

        self.test_user.organizations.append(org)
        self.promote_user(role_name=ROLE.PATIENT.value)

        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc = UserConsent(
            user_id=TEST_USER_ID, organization=org,
            audit=audit, agreement_url='http://no.com',
            research_study_id=0, acceptance_date=now)

        with SessionScope(db):
            db.session.add(qb)
            db.session.add(self.test_user)
            db.session.add(audit)
            db.session.add(uc)
            db.session.commit()
        qb = db.session.merge(qb)

        # create in-progress QNR for User/QB/RP
        mock_qr(
            instrument_id='epic26', status='in-progress',
            timestamp=now, qb=qb)

        # User associated with CRV org should generate appropriate
        # questionnaires
        self.test_user = db.session.merge(self.test_user)
        qb_stat = QB_Status(self.test_user, 0, now)
        qb = qb_stat.current_qbd().questionnaire_bank
        assert qb.research_protocol.name == 'proto'

        # Pointing the User's org to a new QB/RP
        # marking the old RP as retired as of yesterday
        old_rp = OrganizationResearchProtocol.query.filter(
            OrganizationResearchProtocol.organization_id == org_id,
            OrganizationResearchProtocol.research_protocol_id == rp_id).one()
        old_rp.retired_as_of = now - timedelta(days=1)
        rp2 = ResearchProtocol(name='new_proto', research_study_id=0)
        qn2 = self.add_questionnaire(name='epic27')
        with SessionScope(db):
            db.session.add(rp2)
            db.session.commit()
        rp2 = db.session.merge(rp2)
        rp2_id = rp2.id

        qn2, org = map(db.session.merge, (qn2, org))
        qb2 = QuestionnaireBank(
            name='Test Questionnaire Bank 2',
            classification='baseline',
            research_protocol_id=rp2_id,
            start='{"days": 0}',
            overdue='{"days": 7}',
            expired='{"days": 90}')
        qbq2 = QuestionnaireBankQuestionnaire(questionnaire=qn2, rank=0)
        qb2.questionnaires.append(qbq2)

        org.research_protocols.append(rp2)

        with SessionScope(db):
            db.session.add(qb2)
            db.session.add(org)
            db.session.commit()
        qb2 = db.session.merge(qb2)

        # outdated QB/RP should be used as long as User has in-progress QNR
        self.test_user = db.session.merge(self.test_user)
        qb_stat = QB_Status(self.test_user, 0, now)
        qb = qb_stat.current_qbd().questionnaire_bank
        assert qb.name == 'Test Questionnaire Bank'
        assert qb.research_protocol.name == 'proto'

        # completing QNR should result in completed status
        # shouldn't pick up new protocol till next iteration
        mock_qr(
            instrument_id='epic26', status='completed',
            timestamp=now, qb=qb)

        self.test_user = db.session.merge(self.test_user)
        invalidate_users_QBT(TEST_USER_ID, research_study_id='all')
        qb_stat = QB_Status(self.test_user, 0, now)
        qb = qb_stat.current_qbd().questionnaire_bank
        assert qb.name == 'Test Questionnaire Bank'
        assert qb_stat.overall_status == OverallStatus.completed

    def test_outdated_done_indef(self):
        """Confirm completed indefinite counts after RP switch"""

        # boiler plate to create baseline and indef with retired RP
        yesterday = now - timedelta(days=1)
        weekago = now - timedelta(weeks=1)
        org, rp2, rp2_id = self.setup_org_n_rp(
            org_name='testorg', rp_name='v2', retired_as_of=yesterday)
        org, rp3, rp3_id = self.setup_org_n_rp(org=org, rp_name='v3')
        org_id = org.id
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(org)
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc = UserConsent(
            user_id=TEST_USER_ID, organization_id=org_id,
            audit=audit, agreement_url='http://no.com',
            research_study_id=0, acceptance_date=weekago)
        with SessionScope(db):
            db.session.add(audit)
            db.session.add(uc)
            db.session.commit()

        self.setup_qb(
            questionnaire_name='epic23', qb_name='baseline v2',
            classification='baseline', rp_id=rp2_id)
        self.setup_qb(
            questionnaire_name='epic26', qb_name='baseline v3',
            classification='baseline', rp_id=rp3_id)
        qb2_indef = self.setup_qb(
            questionnaire_name='irondemog', qb_name='indef v2',
            classification='indefinite', rp_id=rp2_id)
        self.setup_qb(
            questionnaire_name='irondemog_v3', qb_name='indef v3',
            classification='indefinite', rp_id=rp3_id)

        # for today, should get the v3 baseline
        user = db.session.merge(self.test_user)
        a_s = QB_Status(user=user, research_study_id=0, as_of_date=now)
        assert (['epic26', 'irondemog_v3'] ==
                a_s.instruments_needing_full_assessment(classification='all'))

        # create done QNR for indefinite dated prior to rp transition
        # belonging to older qb - confirm that clears indef work as of then
        mock_qr('irondemog', timestamp=weekago, qb=qb2_indef)
        user = db.session.merge(self.test_user)
        invalidate_users_QBT(user_id=TEST_USER_ID, research_study_id='all')
        a_s = QB_Status(user=user, research_study_id=0, as_of_date=weekago)
        assert (a_s.instruments_needing_full_assessment(
            classification='indefinite') == [])

        # move forward in time; user should no longer need indefinite, even
        # tho RP changed
        qb2_indef = db.session.merge(qb2_indef)
        a_s = QB_Status(user=user, research_study_id=0, as_of_date=now)
        assert qb2_indef == a_s.current_qbd(
            classification='indefinite').questionnaire_bank
        assert (a_s.instruments_needing_full_assessment(
            classification='indefinite') == [])
        assert (a_s.instruments_needing_full_assessment(
            classification='all') == ['epic26'])

    def test_completed_older_rp(self):
        """If current qb completed on older rp, should show as done"""
        fourmonthsago = now - timedelta(days=120)
        weekago = now - timedelta(weeks=1)
        twoweeksago = now - timedelta(weeks=2)
        org = self.setup_org_qbs(rp_name='v2', retired_as_of=weekago)
        org_id = org.id
        self.setup_org_qbs(org=org, rp_name='v3')

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(org)
        audit = Audit(
            user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc = UserConsent(
            user_id=TEST_USER_ID, organization_id=org_id,
            audit=audit, agreement_url='http://no.com',
            research_study_id=0, acceptance_date=fourmonthsago)
        with SessionScope(db):
            db.session.add(audit)
            db.session.add(uc)
            db.session.commit()
        user = db.session.merge(self.test_user)

        # Now, should still be rp v3, 3mo recurrence
        a_s = QB_Status(user=user, research_study_id=0, as_of_date=now)
        assert (a_s.current_qbd().questionnaire_bank.name
                == 'CRV_recurring_3mo_period v3')
        assert a_s.instruments_needing_full_assessment() == [
            'epic26_v3', 'eortc_v3']

        # Complete the questionnaire from the 3mo v2 QB
        v2qb = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == 'CRV_recurring_3mo_period v2').one()
        mock_qr('epic26_v2', timestamp=twoweeksago, qb=v2qb, iteration=0)
        mock_qr('eortc_v2', timestamp=twoweeksago, qb=v2qb, iteration=0)

        # Two weeks ago, should be completed
        user = db.session.merge(user)
        a_s = QB_Status(user=user, research_study_id=0, as_of_date=twoweeksago)
        assert a_s.overall_status == OverallStatus.completed

        # Current should also be completed, even tho protocol changed
        a_s = QB_Status(user=user, research_study_id=0, as_of_date=now)
        assert a_s.overall_status == OverallStatus.completed
