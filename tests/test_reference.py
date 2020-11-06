"""Unit test module for Reference class"""

from portal.models.intervention import Intervention
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.reference import Reference
from portal.system_uri import US_NPI
from tests import TEST_USER_ID, TestCase


class TestReference(TestCase):

    def test_clinician(self):
        patient = Reference.clinician(TEST_USER_ID)
        assert patient.as_fhir()['display'] == self.test_user.display_name

    def test_clinician_parse(self):
        ref = {'reference': f'api/clinician/{TEST_USER_ID}'}
        parsed = Reference.parse(ref)
        assert self.test_user == parsed

    def test_patient(self):
        patient = Reference.patient(TEST_USER_ID)
        assert patient.as_fhir()['display'] == self.test_user.display_name

    def test_organization(self):
        org = Reference.organization(0)
        assert org.as_fhir()['display'] == 'none of the above'

    def test_org_w_identifier(self):
        o = self.prep_org_w_identifier()
        o_ref = Reference.organization(o.id)
        assert o_ref.as_fhir()['display'] == 'test org'
        assert (o_ref.as_fhir()['reference']
                == 'api/organization/{}'.format(o.id))

    def test_org_w_identifier_parse(self):
        o = self.prep_org_w_identifier()
        ref = {'reference': 'api/organization/123-45?system={}'.format(US_NPI)}
        parsed = Reference.parse(ref)
        assert o == parsed

    def test_questionnaire(self):
        q = self.add_questionnaire('epic1000')
        q_ref = Reference.questionnaire(q.name)
        assert q_ref.as_fhir()['display'] == 'epic1000'

    def test_questionnaire_parse(self):
        q = self.add_questionnaire('epiclife')
        ref = {
            'reference':
                'api/questionnaire/{0.value}?system={0.system}'.format(
                    q.identifiers[0])}
        parsed = Reference.parse(ref)
        assert q == parsed

    def test_questionnaire_bank(self):
        q = QuestionnaireBank(name='testy')
        q_ref = Reference.questionnaire_bank(q.name)
        assert q_ref.as_fhir()['display'] == 'testy'

    def test_questionnaire_response(self):
        qnr_id = {
            "system": "https://ae-eproms-test.cirg.washington.edu",
            "value": "588.0"}
        qnr_ref = Reference.questionnaire_response(qnr_id)
        assert qnr_ref.as_fhir()['reference'] == (
            f"{qnr_id['system']}/QuestionnaireResponse/{qnr_id['value']}")

    def test_qnr_parse(self):
        from tests.test_assessment_status import (
            mock_eproms_questionnairebanks,
            mock_qr
        )
        doc_id = '2084.0'

        # boilerplate necessary to persist a QNR
        self.bless_with_basics(make_patient=True)
        mock_eproms_questionnairebanks()
        qb = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == 'localized').one()
        mock_qr('epic26', doc_id=doc_id, qb=qb)

        # confirm [system]/QuestionnaireResponse/[value] pulls
        # the referenced object
        qnr_reference = (
            "https://stg-ae.us.truenth.org/eproms-demo"
            f"/QuestionnaireResponse/{doc_id}")
        ref = {'Reference': qnr_reference}
        parsed = Reference.parse(ref)
        assert parsed.document['identifier']['value'] == doc_id

    def test_intervention(self):
        i = Intervention.query.filter_by(name='self_management').one()
        i_ref = Reference.intervention(i.id)
        assert i_ref.as_fhir()['display'] == 'self_management'
        assert (i_ref.as_fhir()['reference']
                == 'api/intervention/self_management')

    def test_intervention_parse(self):
        ref = {'reference': 'api/intervention/self_management'}
        i = Reference.parse(ref)
        assert i.name == 'self_management'

    def test_practitioner(self):
        p = self.add_practitioner()
        p_ref = Reference.practitioner(p.id)
        assert p_ref.as_fhir()['display'] == 'first last'
        assert (p_ref.as_fhir()['reference']
                == 'api/practitioner/12345?system={}'.format(US_NPI))

    def test_practitioner_parse(self):
        p = self.add_practitioner()
        ref = {'reference': 'api/practitioner/12345?system={}'.format(US_NPI)}
        parsed = Reference.parse(ref)
        assert p == parsed
