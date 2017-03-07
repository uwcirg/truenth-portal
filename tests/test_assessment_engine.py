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
