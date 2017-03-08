"""Unit test module for Assessment Engine API"""
import json
from flask_swagger import swagger
from tests import TestCase, TEST_USER_ID


class TestAssessmentEngine(TestCase):

    def test_submit_assessment(self):
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']

        self.login()
        rv = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data),
        )
        self.assert200(rv)
        response = rv.json
        self.assertEquals(response['ok'], True)
        self.assertEquals(response['valid'], True)

    def test_update_assessment(self):
        swagger_spec = swagger(self.app)
        completed_qnr = swagger_spec['definitions']['QuestionnaireResponse']['example']
        instrument_id = completed_qnr['questionnaire']['reference'].split('/')[-1]
        
        questions = completed_qnr['group']['question']
        incomplete_questions = []

        # Delete answers for second half of QuestionnaireResponse
        for index, question in enumerate(questions):
            question = question.copy()
            if (index > len(questions)/2):
                question.pop('answer', [])
            incomplete_questions.append(question)
        in_progress_qnr = completed_qnr.copy()
        in_progress_qnr.update({
            'status': 'in-progress',
            'group': {'question': incomplete_questions},
        })

        self.login()
        
        # Upload incomplete QNR
        in_progress_response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(in_progress_qnr),
        )

        # Update incomplete QNR
        update_qnr_response = self.client.put(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(completed_qnr),
        )
        self.assert200(update_qnr_response)
        self.assertTrue(update_qnr_response.json['ok'])
        self.assertTrue(update_qnr_response.json['valid'])

        updated_qnr_response = self.client.get(
            '/api/patient/assessment?instrument_id={}'.format(instrument_id),
            content_type='application/json',
        )
        # import ipdb; ipdb.set_trace()
        self.assertEquals(updated_qnr_response.json['entry'][0]['group'], completed_qnr['group'])

    def test_no_update_assessment(self):
        swagger_spec = swagger(self.app)
        qnr = swagger_spec['definitions']['QuestionnaireResponse']['example']

        self.login()

        # Upload QNR
        qnr_response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(qnr),
        )

        qnr['identifier']['system'] = 'foo'

        # Attempt to update different QNR; should fail
        update_qnr_response = self.client.put(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(qnr),
        )
        self.assert404(update_qnr_response)

    def test_assessments_bundle(self):
        swagger_spec = swagger(self.app)
        example_data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        instrument_id = example_data['questionnaire']['reference'].split('/')[-1]

        self.login()
        upload = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(example_data),
        )

        rv = self.client.get(
            '/api/patient/assessment?instrument_id={}'.format(instrument_id),
            content_type='application/json',
        )
        response = rv.json

        self.assertEquals(response['total'], len(response['entry']))
        self.assertTrue(response['entry'][0]['questionnaire']['reference'].endswith(instrument_id))

    def test_assessments_csv(self):
        swagger_spec = swagger(self.app)
        example_data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        instrument_id = example_data['questionnaire']['reference'].split('/')[-1]

        self.login()
        upload_response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(example_data),
        )

        download_response = self.client.get(
            '/api/patient/assessment?format=csv&instrument_id={}'.format(instrument_id),
        )
        csv_string = download_response.data
        self.assertGreater(csv_string.split("\n"), 1)
        # Todo: use csv module for more robust test
