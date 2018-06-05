"""Unit test module for Reference class"""
from flask_webtest import SessionScope
from portal.extensions import db
from portal.models.identifier import Identifier
from portal.models.intervention import Intervention
from portal.models.organization import Organization
from portal.models.practitioner import Practitioner
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.reference import Reference
from portal.system_uri import US_NPI
from tests import TEST_USER_ID, TestCase


class TestReference(TestCase):

    def test_patient(self):
        patient = Reference.patient(TEST_USER_ID)
        self.assertEquals(
            patient.as_fhir()['display'], self.test_user.display_name)

    def test_organization(self):
        org = Reference.organization(0)
        self.assertEquals(
            org.as_fhir()['display'], 'none of the above')

    def test_org_w_identifier(self):
        o = self.prep_org_w_identifier()
        o_ref = Reference.organization(o.id)
        self.assertEquals(
            o_ref.as_fhir()['display'], 'test org')
        self.assertEquals(
            o_ref.as_fhir()['reference'],
            'api/organization/{}'.format(o.id))

    def test_org_w_identifier_parse(self):
        o = self.prep_org_w_identifier()
        ref = {'reference': 'api/organization/123-45?system={}'.format(US_NPI)}
        parsed = Reference.parse(ref)
        self.assertEquals(o, parsed)

    def test_questionnaire(self):
        q = self.add_questionnaire('epic1000')
        q_ref = Reference.questionnaire(q.name)
        self.assertEquals(
            q_ref.as_fhir()['display'], 'epic1000')

    def test_questionnaire_parse(self):
        q = self.add_questionnaire('epiclife')
        ref = {
            'reference':
                'api/questionnaire/{0.value}?system={0.system}'.format(
                    q.identifiers[0])}
        parsed = Reference.parse(ref)
        self.assertEquals(q, parsed)

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
        self.assertEquals(
            i_ref.as_fhir()['reference'], 'api/intervention/self_management')

    def test_intervention_parse(self):
        ref = {'reference': 'api/intervention/self_management'}
        i = Reference.parse(ref)
        self.assertEquals(i.name, 'self_management')

    def test_practioner(self):
        p = self.add_practitioner()
        p_ref = Reference.practitioner(p.id)
        self.assertEquals(
            p_ref.as_fhir()['display'], 'first last')
        self.assertEquals(
            p_ref.as_fhir()['reference'],
            'api/practitioner/12345?system={}'.format(US_NPI))

    def test_practitioner_parse(self):
        p = self.add_practitioner()
        ref = {'reference': 'api/practitioner/12345?system={}'.format(US_NPI)}
        parsed = Reference.parse(ref)
        self.assertEquals(p, parsed)
