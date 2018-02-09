"""Unit test module for questionnaire_bank"""
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.fhir import CC
from portal.models.intervention import Intervention
from portal.models.organization import Organization
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import QuestionnaireBank, visit_name
from portal.models.questionnaire_bank import QuestionnaireBankQuestionnaire
from portal.models.recur import Recur
from portal.models.research_protocol import ResearchProtocol
from portal.system_uri import ICHOM
from tests import TestCase, TEST_USER_ID


class TestQuestionnaireBank(TestCase):

    def test_org_trigger_date(self):
        # testing org-based QBs
        rp = ResearchProtocol(name='proto')
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        q = Questionnaire(name='q')
        org = Organization(name='org', research_protocol_id=rp_id)
        with SessionScope(db):
            db.session.add(q)
            db.session.add(org)
            db.session.commit()
        q, org, self.test_user = map(db.session.merge,
                                     (q, org, self.test_user))
        qb = QuestionnaireBank(
            name='qb', research_protocol_id=rp_id, classification='baseline',
            start='{"days": 1}', expired='{"days": 2}')
        qbq = QuestionnaireBankQuestionnaire(rank=0, questionnaire=q)
        qb.questionnaires.append(qbq)

        # user without consents or TX date should return None
        self.assertFalse(qb.trigger_date(self.test_user))

        # user with consent should return consent date
        now = datetime.utcnow()
        self.consent_with_org(org.id, setdate=now)
        self.test_user = db.session.merge(self.test_user)
        self.assertEquals(qb.trigger_date(self.test_user), now)

        # user with consent and TX date should return TX date (if qb.recurs)
        tx_date = datetime(2017, 6, 10, 20, 00, 00, 000000)
        self.add_procedure(code='7', display='Focal therapy',
                           system=ICHOM, setdate=tx_date)
        self.test_user = db.session.merge(self.test_user)
        qb.__trigger_date = None  # clear out stored trigger_date
        recur = Recur(
            start='{"months": 3}', cycle_length='{"months": 6}',
            termination='{"months": 24}')
        qb.recurs.append(recur)
        self.assertEquals(qb.trigger_date(self.test_user), tx_date)

    def test_intervention_trigger_date(self):
        # testing intervention-based QBs
        q = Questionnaire(name='q')
        interv = Intervention(name='interv', description='test')
        with SessionScope(db):
            db.session.add(q)
            db.session.add(interv)
            db.session.commit()
        q, interv, self.test_user = map(db.session.merge,
                                        (q, interv, self.test_user))
        qb = QuestionnaireBank(
            name='qb', intervention_id=interv.id, classification='baseline',
            start='{"days": 1}', expired='{"days": 2}')
        qbq = QuestionnaireBankQuestionnaire(rank=0, questionnaire=q)
        qb.questionnaires.append(qbq)

        # user without biopsy or TX date should return None
        self.assertFalse(qb.trigger_date(self.test_user))

        # user with biopsy should return biopsy date
        self.login()
        self.test_user.save_constrained_observation(
            codeable_concept=CC.BIOPSY, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
            status='')
        self.test_user = db.session.merge(self.test_user)
        obs = self.test_user.observations.first()
        self.assertEquals(obs.codeable_concept.codings[0].display, 'biopsy')
        self.assertEquals(qb.trigger_date(self.test_user), obs.issued)

        # user with biopsy and TX date should return TX date
        tx_date = datetime.utcnow()
        self.add_procedure(code='7', display='Focal therapy',
                           system=ICHOM, setdate=tx_date)
        self.test_user = db.session.merge(self.test_user)
        qb.__trigger_date = None  # clear out stored trigger_date
        self.assertEquals(qb.trigger_date(self.test_user), tx_date)

    def test_start(self):
        rp = ResearchProtocol(name='proto')
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        q = Questionnaire(name='q')
        org = Organization(name='org', research_protocol_id=rp_id)
        with SessionScope(db):
            db.session.add(q)
            db.session.add(org)
            db.session.commit()
        q, org = map(db.session.merge, (q, org))
        qb = QuestionnaireBank(
            name='qb', research_protocol_id=rp_id, classification='baseline',
            start='{"days": 1}', expired='{"days": 2}')
        qbq = QuestionnaireBankQuestionnaire(rank=0, questionnaire=q)
        qb.questionnaires.append(qbq)

        trigger_date = datetime.strptime('2000-01-01', '%Y-%m-%d')
        now = datetime.utcnow()
        start = qb.calculated_start(
            trigger_date, as_of_date=now).relative_start
        self.assertTrue(start > trigger_date)
        self.assertEquals(start, datetime.strptime('2000-01-02', '%Y-%m-%d'))

        end = qb.calculated_expiry(trigger_date, as_of_date=now)
        expected_expiry = datetime.strptime('2000-01-04', '%Y-%m-%d')
        self.assertEquals(end, expected_expiry)

    def test_due(self):
        rp = ResearchProtocol(name='proto')
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        q = Questionnaire(name='q')
        org = Organization(name='org', research_protocol_id=rp_id)
        with SessionScope(db):
            db.session.add(q)
            db.session.add(org)
            db.session.commit()
        q, org = map(db.session.merge, (q, org))
        qb = QuestionnaireBank(
            name='qb', research_protocol_id=rp_id, classification='baseline',
            start='{"days": 1}', due='{"days": 2}')
        qbq = QuestionnaireBankQuestionnaire(rank=0, questionnaire=q)
        qb.questionnaires.append(qbq)

        trigger_date = datetime.strptime('2000-01-01', '%Y-%m-%d')
        now = datetime.now()
        start = qb.calculated_start(
            trigger_date, as_of_date=now).relative_start
        self.assertTrue(start > trigger_date)
        self.assertEquals(start, datetime.strptime('2000-01-02', '%Y-%m-%d'))

        due = qb.calculated_due(trigger_date, as_of_date=now)
        expected_due = datetime.strptime('2000-01-04', '%Y-%m-%d')
        self.assertEquals(due, expected_due)

    def test_questionnaire_serialize(self):
        q1 = Questionnaire(name='q1')
        with SessionScope(db):
            db.session.add(q1)
            db.session.commit()
        q1 = db.session.merge(q1)
        data = q1.as_fhir()
        self.assertEquals(data['resourceType'], "Questionnaire")
        self.assertEquals(data['name'], 'q1')

    def test_serialize(self):
        rp = ResearchProtocol(name='proto')
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        q1 = Questionnaire(name='q1')
        q2 = Questionnaire(name='q2')
        org = Organization(name='org', research_protocol_id=rp_id)
        with SessionScope(db):
            db.session.add(q1)
            db.session.add(q2)
            db.session.add(org)
            db.session.commit()
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
        self.assertEquals('QuestionnaireBank', data.get('resourceType'))
        self.assertEquals(2, len(data['questionnaires']))

    def test_import(self):
        rp = ResearchProtocol(name='proto')
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id
        rp_name = rp.name

        org = Organization(name='org', research_protocol_id=rp_id)
        q1 = Questionnaire(name='q1')
        q2 = Questionnaire(name='q2')
        with SessionScope(db):
            db.session.add(org)
            db.session.add(q1)
            db.session.add(q2)
            db.session.commit()
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
                        'reference': 'api/questionnaire/{}'.format(
                            q1.name)}
                },
                {
                    'rank': 1,
                    'questionnaire': {
                        'reference': 'api/questionnaire/{}'.format(
                            q2.name)}
                }
            ],
            'id': 1,
            'name': u'bank',
            'classification': 'baseline'
        }
        qb = QuestionnaireBank.from_json(data)
        self.assertEquals(2, len(qb.questionnaires))

    def test_import_followup(self):
        intervention = Intervention(name='testy', description='simple')
        q1 = Questionnaire(name='q1')
        q2 = Questionnaire(name='q2')
        with SessionScope(db):
            db.session.add(intervention)
            db.session.add(q1)
            db.session.add(q2)
            db.session.commit()
        intervention, q1, q2 = map(db.session.merge, (intervention, q1, q2))

        data = {
            'resourceType': 'QuestionnaireBank',
            'intervention': {'reference': 'api/intervention/{}'.format(
                intervention.name)},
            'expired': '{"days": 104}',
            'start': '{"days": 76}',
            'questionnaires': [
                {
                    'rank': 2,
                    'questionnaire': {
                        'reference': 'api/questionnaire/{}'.format(
                            q1.name)}
                },
                {
                    'rank': 1,
                    'questionnaire': {
                        'reference': 'api/questionnaire/{}'.format(
                            q2.name)}
                }
            ],
            'id': 1,
            'name': u'bank',
            'classification': 'followup'
        }
        qb = QuestionnaireBank.from_json(data)
        self.assertEquals(2, len(qb.questionnaires))

    def test_lookup_for_user(self):
        rp = ResearchProtocol(name='proto')
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        crv = Organization(name='CRV', research_protocol_id=rp_id)
        epic26 = Questionnaire(name='epic26')
        eproms_add = Questionnaire(name='eproms_add')
        comorb = Questionnaire(name='comorb')
        with SessionScope(db):
            db.session.add(crv)
            db.session.add(epic26)
            db.session.add(eproms_add)
            db.session.add(comorb)
            db.session.commit()
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

        self.test_user.organizations.append(crv)
        self.consent_with_org(org_id=crv.id)
        with SessionScope(db):
            db.session.add(bank)
            db.session.commit()

        # User associated with CRV org should generate appropriate
        # questionnaires
        self.test_user = db.session.merge(self.test_user)
        qb = QuestionnaireBank.most_current_qb(
            self.test_user, as_of_date=None).questionnaire_bank
        results = list(qb.questionnaires)
        self.assertEquals(3, len(results))
        # confirm rank sticks
        self.assertEquals(results[0].name, 'epic26')
        self.assertEquals(results[2].name, 'comorb')

    def test_lookup_with_intervention(self):
        intv = Intervention(name='TEST', description='Test Intervention')
        epic26 = Questionnaire(name='epic26')
        eproms_add = Questionnaire(name='eproms_add')
        with SessionScope(db):
            db.session.add(intv)
            db.session.add(epic26)
            db.session.add(eproms_add)
            db.session.commit()
        intv, epic26, eproms_add = map(
            db.session.merge, (intv, epic26, eproms_add))

        bank = QuestionnaireBank(
            name='CRV', intervention_id=intv.id,
            start='{"days": 7}',
            expired='{"days": 90}')
        for rank, q in enumerate((epic26, eproms_add)):
            qbq = QuestionnaireBankQuestionnaire(
                questionnaire_id=q.id,
                rank=rank)
            bank.questionnaires.append(qbq)

        self.test_user.interventions.append(intv)
        self.login()
        self.add_required_clinical_data()
        with SessionScope(db):
            db.session.add(bank)
            db.session.commit()

        # User associated with INTV intervention should generate appropriate
        # questionnaires
        self.test_user = db.session.merge(self.test_user)
        qb = QuestionnaireBank.most_current_qb(
            self.test_user, as_of_date=None).questionnaire_bank
        results = list(qb.questionnaires)
        self.assertEquals(2, len(results))

    def test_questionnaire_gets(self):
        rp = ResearchProtocol(name='proto')
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        crv = Organization(name='CRV', research_protocol_id=rp_id)
        epic26 = Questionnaire(name='epic26')
        eproms_add = Questionnaire(name='eproms_add')
        comorb = Questionnaire(name='comorb')
        with SessionScope(db):
            db.session.add(crv)
            db.session.add(epic26)
            db.session.add(eproms_add)
            db.session.add(comorb)
            db.session.commit()
        crv, epic26, eproms_add, comorb = map(
            db.session.merge, (crv, epic26, eproms_add, comorb))

        resp = self.client.get('/api/questionnaire')
        self.assert200(resp)
        self.assertEquals(len(resp.json['entry']), 3)

        resp = self.client.get('/api/questionnaire/{}'.format('epic26'))
        self.assert200(resp)
        self.assertEquals(resp.json['questionnaire']['name'], 'epic26')

        bank = QuestionnaireBank(name='CRV', research_protocol_id=rp_id,
                                 start='{"days": 7}',
                                 expired='{"days": 90}')
        for rank, q in enumerate((epic26, eproms_add, comorb)):
            qbq = QuestionnaireBankQuestionnaire(
                questionnaire_id=q.id,
                rank=rank)
            bank.questionnaires.append(qbq)

        self.test_user.organizations.append(crv)
        with SessionScope(db):
            db.session.add(bank)
            db.session.commit()

        resp = self.client.get('/api/questionnaire_bank')
        self.assert200(resp)
        self.assertEquals(len(resp.json['entry'][0]['questionnaires']), 3)

    def test_visit_baseline(self):
        crv = setup_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user.organizations.append(crv)
        self.test_user = db.session.merge(self.test_user)

        qbd = QuestionnaireBank.most_current_qb(
            self.test_user, as_of_date=None)
        self.assertEquals("Baseline", visit_name(qbd))

    def test_visit_3mo(self):
        crv = setup_qbs()
        self.bless_with_basics(backdate=relativedelta(months=3))
        self.test_user.organizations.append(crv)
        self.test_user = db.session.merge(self.test_user)

        qbd = QuestionnaireBank.most_current_qb(
            self.test_user, as_of_date=None)
        self.assertEquals("Month 3", visit_name(qbd))

        qbd_i2 = qbd._replace(iteration=1)
        self.assertEquals("Month 9", visit_name(qbd_i2))

    def test_visit_6mo(self):
        crv = setup_qbs()
        self.bless_with_basics(backdate=relativedelta(months=6))
        self.test_user.organizations.append(crv)
        self.test_user = db.session.merge(self.test_user)

        qbd = QuestionnaireBank.most_current_qb(
            self.test_user, as_of_date=None)
        self.assertEquals("Month 6", visit_name(qbd))

        qbd_i2 = qbd._replace(iteration=1)
        self.assertEquals("Month 18", visit_name(qbd_i2))

    def test_user_current_qb(self):
        crv = setup_qbs()
        self.bless_with_basics(backdate=relativedelta(months=3))
        self.test_user.organizations.append(crv)
        self.test_user = db.session.merge(self.test_user)

        self.login()
        resp = self.client.get('/api/user/{}/'
                               'questionnaire_bank'.format(TEST_USER_ID))
        self.assert200(resp)
        self.assertEquals(resp.json['questionnaire_bank']['name'],
                          'CRV_recurring_3mo_period')

        dt = (datetime.utcnow() - relativedelta(months=2)).strftime('%Y-%m-%d')
        resp2 = self.client.get('/api/user/{}/questionnaire_bank?as_of_date='
                                '{}'.format(TEST_USER_ID, dt))
        self.assert200(resp2)
        self.assertEquals(resp2.json['questionnaire_bank']['name'],
                          'CRV Baseline')

        dt = (datetime.utcnow() - relativedelta(months=4)).strftime('%Y-%m-%d')
        resp3 = self.client.get('/api/user/{}/questionnaire_bank?as_of_date='
                                '{}'.format(TEST_USER_ID, dt))
        self.assert200(resp3)
        self.assertFalse(resp3.json['questionnaire_bank'])


def setup_qbs():
    rp = ResearchProtocol(name='proto')
    with SessionScope(db):
        db.session.add(rp)
        db.session.commit()
    rp = db.session.merge(rp)
    rp_id = rp.id

    crv = Organization(name='CRV', research_protocol_id=rp_id)
    epic26 = Questionnaire(name='epic26')
    recur3 = Recur(
        start='{"months": 3}', cycle_length='{"months": 6}',
        termination='{"months": 24}')
    recur6 = Recur(
        start='{"months": 6}', cycle_length='{"years": 1}',
        termination='{"years": 3, "months": 3}')

    with SessionScope(db):
        db.session.add(crv)
        db.session.add(epic26)
        db.session.add(recur3)
        db.session.add(recur6)
        db.session.commit()
    crv, epic26, recur3, recur6 = map(
        db.session.merge, (crv, epic26, recur3, recur6))

    qb_base = QuestionnaireBank(
        name='CRV Baseline',
        classification='baseline',
        research_protocol_id=rp_id,
        start='{"days": 0}',
        overdue='{"days": 30}',
        expired='{"months": 3}')
    qbq = QuestionnaireBankQuestionnaire(questionnaire=epic26, rank=0)
    qb_base.questionnaires.append(qbq)

    qb_m3 = QuestionnaireBank(
        name='CRV_recurring_3mo_period',
        classification='recurring',
        research_protocol_id=rp_id,
        start='{"days": 0}',
        overdue='{"days": 30}',
        expired='{"months": 3}',
        recurs=[recur3])
    qbq = QuestionnaireBankQuestionnaire(questionnaire=epic26, rank=0)
    qb_m3.questionnaires.append(qbq)

    qb_m6 = QuestionnaireBank(
        name='CRV_recurring_6mo_period',
        classification='recurring',
        research_protocol_id=rp_id,
        start='{"days": 0}',
        overdue='{"days": 30}',
        expired='{"months": 3}',
        recurs=[recur6])
    qbq = QuestionnaireBankQuestionnaire(questionnaire=epic26, rank=0)
    qb_m6.questionnaires.append(qbq)

    with SessionScope(db):
        db.session.add(qb_base)
        db.session.add(qb_m3)
        db.session.add(qb_m6)
        db.session.commit()
    qb_base, qb_m3, qb_m6 = map(
        db.session.merge, (qb_base, qb_m3, qb_m6))

    return crv
