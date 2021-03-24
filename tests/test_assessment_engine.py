"""Unit test module for Assessment Engine API"""
from datetime import datetime
import json
import os

from dateutil.relativedelta import relativedelta
from flask_swagger import swagger
from flask_webtest import SessionScope
import jsonschema
import pytest

from portal.date_tools import FHIR_datetime
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.identifier import Identifier
from portal.models.organization import Organization
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
    QuestionnaireBankQuestionnaire,
)
from portal.models.questionnaire_response import (
    QuestionnaireResponse,
    qnr_csv_column_headers,
)
from portal.models.research_protocol import ResearchProtocol
from portal.models.role import ROLE
from portal.models.user import User
from portal.models.user_consent import UserConsent
from portal.system_uri import (
    TRUENTH_STATUS_EXTENSION,
    TRUENTH_VISIT_NAME_EXTENSION,
)
from tests import TEST_USER_ID, TestCase


class TestAssessmentEngine(TestCase):

    def test_qnr_validation(self):
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        QuestionnaireResponse.validate_document(data)

    def test_qnr_invalidation(self):
        with open(os.path.join(os.path.dirname(
                __file__), 'bad_qnr.json'), 'r') as fhir_data:
            data = json.load(fhir_data)
        with pytest.raises(jsonschema.ValidationError):
            QuestionnaireResponse.validate_document(data)

    def test_submit_assessment(self):
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 200
        response = response.json
        assert response['ok']
        assert response['valid']
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.questionnaire_responses.count() == 1
        assert (
            self.test_user.questionnaire_responses[0].encounter.auth_method
            == 'password_authenticated')

    def test_submit_invalid_assessment(self):
        data = {'no_questionnaire_field': True}

        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 400

    def test_invalid_status(self):
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data.pop('identifier')
        data['status'] = 'in-progress'

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 400

    def test_invalid_format(self):
        with open(os.path.join(os.path.dirname(
                __file__), 'bad_qnr.json'), 'r') as fhir_data:
            data = json.load(fhir_data)
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 400

        # Confirm accessing the user's assessments doesn't raise
        updated_qnr_response = self.client.get(
            '/api/patient/{}/assessment/epic26'.format(TEST_USER_ID))
        assert updated_qnr_response.status_code == 200

    def test_duplicate_identifier(self):
        swagger_spec = swagger(self.app)
        identifier = Identifier(system='https://unique.org', value='abc123')
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data['identifier'] = identifier.as_fhir()

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 200

        # Submit a second, with the same identifier, expect error
        data2 = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data2['identifier'] = identifier.as_fhir()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data2)
        assert response.status_code == 409
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.questionnaire_responses.count() == 1

        # And a third, with just the id.value changed
        data3 = swagger_spec['definitions']['QuestionnaireResponse']['example']
        identifier.value = 'do-over'
        data3['identifier'] = identifier.as_fhir()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data3)
        assert response.status_code == 200
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.questionnaire_responses.count() == 2

    def test_invalid_identifier(self):
        swagger_spec = swagger(self.app)
        identifier = Identifier(system=None, value='abc-123')
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data['identifier'] = identifier.as_fhir()

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 400

    def test_qnr_extensions(self):
        """User with expired, in-process QNR should include extensions"""
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data['status'] = 'in-progress'

        rp = ResearchProtocol(name='proto', research_study_id=0)
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        qn = self.add_questionnaire(name='epic26')
        org = Organization(name="testorg")
        org.research_protocols.append(rp)
        with SessionScope(db):
            db.session.add(qn)
            db.session.add(org)
            db.session.commit()

        qn, org = map(db.session.merge, (qn, org))
        qb = QuestionnaireBank(
            name='Test Questionnaire Bank',
            classification='baseline',
            research_protocol_id=rp_id,
            start='{"days": 0}',
            overdue='{"days": 7}',
            expired='{"days": 90}')
        qbq = QuestionnaireBankQuestionnaire(questionnaire=qn, rank=0)
        qb.questionnaires.append(qbq)

        test_user = User.query.get(TEST_USER_ID)
        test_user.organizations.append(org)
        authored = FHIR_datetime.parse(data['authored'])
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc = UserConsent(
            user_id=TEST_USER_ID, organization=org,
            audit=audit, agreement_url='http://no.com',
            research_study_id=0,
            acceptance_date=authored - relativedelta(days=30))

        with SessionScope(db):
            db.session.add(qb)
            db.session.add(test_user)
            db.session.add(audit)
            db.session.add(uc)
            db.session.commit()

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 200

        # request for the user's QNR bundle should include the one, with
        # appropriate extensions
        response = self.client.get(
            '/api/patient/{}/assessment'.format(TEST_USER_ID))
        assert 1 == len(response.json['entry'])
        assert 'extension' in response.json['entry'][0]
        extensions = response.json['entry'][0]['extension']
        visit = [
            e for e in extensions
            if e.get('url') == TRUENTH_VISIT_NAME_EXTENSION]
        assert 1 == len(visit)
        assert visit[0]['visit_name'] == 'Baseline'

        status = [
            e for e in extensions
            if e.get('url') == TRUENTH_STATUS_EXTENSION]
        assert 1 == len(status)
        assert status[0]['status'] == 'partially_completed'

    def test_submit_assessment_for_qb(self):
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']

        rp = ResearchProtocol(name='proto', research_study_id=0)
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        qn = self.add_questionnaire(name='epic26')
        org = Organization(name="testorg")
        org.research_protocols.append(rp)
        with SessionScope(db):
            db.session.add(qn)
            db.session.add(org)
            db.session.commit()

        qn, org = map(db.session.merge, (qn, org))
        qb = QuestionnaireBank(
            name='Test Questionnaire Bank',
            classification='baseline',
            research_protocol_id=rp_id,
            start='{"days": 0}',
            overdue='{"days": 7}',
            expired='{"days": 90}')
        qbq = QuestionnaireBankQuestionnaire(questionnaire=qn, rank=0)
        qb.questionnaires.append(qbq)

        test_user = User.query.get(TEST_USER_ID)
        test_user.organizations.append(org)
        authored = FHIR_datetime.parse(data['authored'])
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc = UserConsent(
            user_id=TEST_USER_ID, organization=org,
            audit=audit, agreement_url='http://no.com',
            research_study_id=0,
            acceptance_date=authored)

        with SessionScope(db):
            db.session.add(qb)
            db.session.add(test_user)
            db.session.add(audit)
            db.session.add(uc)
            db.session.commit()

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 200
        test_user = User.query.get(TEST_USER_ID)
        qb = db.session.merge(qb)
        assert test_user.questionnaire_responses.count() == 1
        assert (
            test_user.questionnaire_responses[0].questionnaire_bank_id
            == qb.id)
        assert test_user.questionnaire_responses[0].qb_iteration is None

    def test_submit_assessment_outside_window(self):
        """Submit assessment outside QB window, confirm no QB assignment"""
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']

        rp = ResearchProtocol(name='proto', research_study_id=0)
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        qn = self.add_questionnaire(name='epic26')
        org = Organization(name="testorg")
        org.research_protocols.append(rp)
        with SessionScope(db):
            db.session.add(qn)
            db.session.add(org)
            db.session.commit()

        qn, org = map(db.session.merge, (qn, org))
        qb = QuestionnaireBank(
            name='Test Questionnaire Bank',
            classification='baseline',
            research_protocol_id=rp_id,
            start='{"days": 0}',
            overdue='{"days": 7}',
            expired='{"days": 90}')
        qbq = QuestionnaireBankQuestionnaire(questionnaire=qn, rank=0)
        qb.questionnaires.append(qbq)

        test_user = User.query.get(TEST_USER_ID)
        test_user.organizations.append(org)
        authored = FHIR_datetime.parse(data['authored'])
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc = UserConsent(
            user_id=TEST_USER_ID, organization=org,
            audit=audit, agreement_url='http://no.com',
            research_study_id=0,
            acceptance_date=authored - relativedelta(days=91))

        with SessionScope(db):
            db.session.add(qb)
            db.session.add(test_user)
            db.session.add(audit)
            db.session.add(uc)
            db.session.commit()

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 200
        test_user = User.query.get(TEST_USER_ID)
        assert test_user.questionnaire_responses.count() == 1
        assert (
            test_user.questionnaire_responses[0].questionnaire_bank_id
            == 0)
        assert test_user.questionnaire_responses[0].qb_iteration is None

    def test_submit_future_assessment(self):
        """Submit assessment with future date should fail"""
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']

        # bump authored to future value
        data['authored'] = FHIR_datetime.as_fhir(
            datetime.utcnow() + relativedelta(days=1))

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 400
        assert "future" in response.json.get('message')

    def test_submit_nearfuture_assessment(self):
        """Submit assessment within a min in future should be allowed"""
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']

        # bump authored to future value within 1 min buffer
        data['authored'] = FHIR_datetime.as_fhir(
            datetime.utcnow() + relativedelta(seconds=52))

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 200

    def test_update_assessment(self):
        swagger_spec = swagger(self.app)
        completed_qnr = swagger_spec['definitions']['QuestionnaireResponse'][
            'example']
        instrument_id = (completed_qnr['questionnaire']['reference'].split(
            '/')[-1])

        questions = completed_qnr['group']['question']
        incomplete_questions = []

        # Delete answers for second half of QuestionnaireResponse
        for index, question in enumerate(questions):
            question = question.copy()
            if (index > len(questions) / 2):
                question.pop('answer', [])
            incomplete_questions.append(question)
        in_progress_qnr = completed_qnr.copy()
        in_progress_qnr.update({
            'status': 'in-progress',
            'group': {'question': incomplete_questions},
        })

        self.login()
        self.bless_with_basics()
        self.promote_user(role_name=ROLE.STAFF.value)
        self.promote_user(role_name=ROLE.RESEARCHER.value)
        self.add_system_user()

        # Upload incomplete QNR
        in_progress_response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            json=in_progress_qnr)
        assert in_progress_response.status_code == 200

        # Update incomplete QNR
        update_qnr_response = self.client.put(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            json=completed_qnr)
        assert update_qnr_response.status_code == 200
        assert update_qnr_response.json['ok']
        assert update_qnr_response.json['valid']

        updated_qnr_response = self.results_from_async_call(
            '/api/patient/assessment',
            query_string={'instrument_id': instrument_id})
        assert updated_qnr_response.status_code == 200
        assert (
            updated_qnr_response.json['entry'][0]['group']
            == completed_qnr['group'])

    def test_no_update_assessment(self):
        swagger_spec = swagger(self.app)
        qnr = swagger_spec['definitions']['QuestionnaireResponse']['example']

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()

        # Upload QNR
        qnr_response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=qnr)
        assert qnr_response.status_code == 200

        qnr['identifier']['system'] = 'foo'

        # Attempt to update different QNR; should fail
        update_qnr_response = self.client.put(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=qnr)
        assert update_qnr_response.status_code == 404

    @pytest.mark.timeout(60)
    def test_assessments_bundle(self):
        swagger_spec = swagger(self.app)
        example_data = swagger_spec['definitions']['QuestionnaireResponse'][
            'example']
        instrument_id = example_data['questionnaire']['reference'].split('/')[
            -1]

        self.login()
        self.bless_with_basics()
        self.promote_user(role_name=ROLE.STAFF.value)
        self.promote_user(role_name=ROLE.RESEARCHER.value)
        self.add_system_user()

        upload = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            json=example_data)
        assert upload.status_code == 200

        response = self.results_from_async_call(
            '/api/patient/assessment',
            query_string={'instrument_id': instrument_id})
        assert response.status_code == 200
        response = response.json

        assert response['total'] == len(response['entry'])
        assert (response['entry'][0]['questionnaire']['reference'].endswith(
            instrument_id))

    def test_assessments_csv(self):
        swagger_spec = swagger(self.app)
        example_data = swagger_spec['definitions']['QuestionnaireResponse'][
            'example']
        instrument_id = example_data['questionnaire']['reference'].split('/')[
            -1]

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.promote_user(role_name=ROLE.RESEARCHER.value)
        self.add_system_user()
        self.login()
        upload_response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            json=example_data)
        assert upload_response.status_code == 200

        download_response = self.results_from_async_call(
            '/api/patient/assessment',
            query_string={'format': 'csv', 'instrument_id': instrument_id}
        )
        csv_string = download_response.get_data(as_text=True)
        # First line should match expected headers
        lines = csv_string.split('\n')
        assert lines[0] == ','.join(qnr_csv_column_headers)
        assert len(csv_string.split("\n")) > 1
        # Todo: use csv module for more robust test
