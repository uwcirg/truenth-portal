"""Unit test module for Assessment Engine API"""
import json
import os
from tests import TestCase, TEST_USER_ID


class TestAssessmentEngine(TestCase):

    def test_assessment_PUT(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'assessment_example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        self.login()
        rv = self.app.put('/api/patient/{}/assessment'.format(TEST_USER_ID),
                         content_type='application/json',
                         data=json.dumps(data))
        self.assert200(rv)
        response = rv.json
        self.assertEquals(response['ok'], True)
        self.assertEquals(response['valid'], True)
