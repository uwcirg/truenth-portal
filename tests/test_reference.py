"""Unit test module for Reference class"""
from tests import TestCase, TEST_USER_ID

from portal.models.intervention import Intervention
from portal.models.reference import Reference
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import QuestionnaireBank


class TestDemographics(TestCase):

    def test_patient(self):
        patient = Reference.patient(TEST_USER_ID)
        self.assertEquals(
            patient.as_fhir()['display'], self.test_user.display_name)

    def test_organization(self):
        org = Reference.organization(0)
        self.assertEquals(
            org.as_fhir()['display'], 'none of the above')

    def test_questionnaire(self):
        q = Questionnaire(name='testy')
        q_ref = Reference.questionnaire(q.name)
        self.assertEquals(
            q_ref.as_fhir()['display'], 'testy')

    def test_questionnaire_bank(self):
        q = QuestionnaireBank(name='testy')
        q_ref = Reference.questionnaire_bank(q.name)
        self.assertEquals(
            q_ref.as_fhir()['display'], 'testy')

    def test_intervention(self):
        i = Intervention.query.filter_by(name='self_management').one()
        i_ref = Reference.intervention(i.id)
        self.assertEquals(
            i_ref.as_fhir()['display'], 'self_management')
