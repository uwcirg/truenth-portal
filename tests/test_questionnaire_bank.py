"""Unit test module for questionnaire_bank"""
from datetime import datetime
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.intervention import Intervention
from portal.models.organization import Organization
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.questionnaire_bank import QuestionnaireBankQuestionnaire
from tests import TestCase


class TestQuestionnaireBank(TestCase):

    def test_start(self):
        q = Questionnaire(name='q')
        org = Organization(name='org')
        with SessionScope(db):
            db.session.add(q)
            db.session.add(org)
            db.session.commit()
        q, org = map(db.session.merge, (q, org))
        qb = QuestionnaireBank(
            name='qb', organization_id=org.id, classification='baseline',
            start='{"days": 1}', expired='{"days": 2}')
        qbq = QuestionnaireBankQuestionnaire(rank=0, questionnaire=q)
        qb.questionnaires.append(qbq)

        trigger_date = datetime.strptime('2000-01-01', '%Y-%m-%d')
        start = qb.calculated_start(trigger_date).relative_start
        self.assertTrue(start > trigger_date)
        self.assertEquals(start, datetime.strptime('2000-01-02', '%Y-%m-%d'))

        end = qb.calculated_expiry(trigger_date)
        expected_expiry = datetime.strptime('2000-01-04', '%Y-%m-%d')
        self.assertEquals(end, expected_expiry)

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
        q1 = Questionnaire(name='q1')
        q2 = Questionnaire(name='q2')
        org = Organization(name='org')
        with SessionScope(db):
            db.session.add(q1)
            db.session.add(q2)
            db.session.add(org)
            db.session.commit()
        q1, q2, org = map(db.session.merge, (q1, q2, org))
        qb = QuestionnaireBank(
            name='qb', organization_id=org.id, classification='baseline',
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
        org = Organization(name='org')
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
            'organization': {'reference': 'api/organization/{}'.format(
                org.id)},
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
        crv = Organization(name='CRV')
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
            name='CRV', organization_id=crv.id,
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
        qb = QuestionnaireBank.most_current_qb(self.test_user).questionnaire_bank
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
        qb = QuestionnaireBank.most_current_qb(self.test_user).questionnaire_bank
        results = list(qb.questionnaires)
        self.assertEquals(2, len(results))

    def test_questionnaire_gets(self):
        crv = Organization(name='CRV')
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

        bank = QuestionnaireBank(name='CRV', organization_id=crv.id,
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
