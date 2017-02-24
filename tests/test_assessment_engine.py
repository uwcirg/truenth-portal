"""Unit test module for Assessment Engine API"""
import json
from flask_swagger import swagger
from tests import TestCase, TEST_USER_ID


class TestAssessmentEngine(TestCase):

    def test_assessment_PUT(self):
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']

        self.login()
        rv = self.client.put(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data),
        )
        self.assert200(rv)
        response = rv.json
        self.assertEquals(response['ok'], True)
        self.assertEquals(response['valid'], True)
