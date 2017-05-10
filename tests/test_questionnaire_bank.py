"""Unit test module for questionnaire_bank"""
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.organization import Organization
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.questionnaire_bank import QuestionnaireBankQuestionnaire
from tests import TestCase


class TestQuestionnaireBank(TestCase):

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
            name='qb', organization_id=org.id, classification='baseline')
        for rank, q in enumerate((q1, q2)):
            qbq = QuestionnaireBankQuestionnaire(
                days_till_due=5,
                days_till_overdue=30,
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
        q2_id = q2.id

        data = {
            'resourceType': 'QuestionnaireBank',
            'organization': {'reference': 'api/organization/{}'.format(
            org.id)},
            'questionnaires': [
                {
                    'days_till_overdue': 30,
                    'days_till_due': 5,
                    'rank': 2,
                    'questionnaire': {
                        'reference': 'api/questionnaire/{}'.format(
                            q1.name)}
                },
                {
                    'days_till_overdue': 30,
                    'days_till_due': 5,
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

        bank = QuestionnaireBank(name='CRV', organization_id=crv.id)
        for rank, q in enumerate((epic26, eproms_add, comorb)):
            qbq = QuestionnaireBankQuestionnaire(
                questionnaire_id=q.id,
                days_till_due=7,
                days_till_overdue=90,
                rank=rank)
            bank.questionnaires.append(qbq)

        self.test_user.organizations.append(crv)
        with SessionScope(db):
            db.session.add(bank)
            db.session.commit()

        # User associated with CRV org should generate appropriate
        # questionnaires
        self.test_user = db.session.merge(self.test_user)
        results = QuestionnaireBank.q_for_user(self.test_user).get('baseline')
        self.assertTrue(3, len(results))
        # confirm rank sticks
        self.assertEquals(results[0].name, 'epic26')
        self.assertEquals(results[2].name, 'comorb')
