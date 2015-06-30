import json
import os
import tempfile
import unittest

import app

class PortalTestCase(unittest.TestCase):

    def setUp(self):
        app.app.config['TESTING'] = True
        app.init_db()

    def tearDown(self):
        pass

    def test_demographics(self):
        # currently cheating - the test user lives at 'id' 5
        # TODO: push test user values into the database.
        with app.app.test_client() as c:
            with c.session_transaction() as sess:
                sess['id'] = '5'

            rv = c.get('/api/demographics')
        fhir = json.loads(rv.data)
        self.assertEquals(len(fhir['identifier']), 2)
        self.assertEquals(fhir['resourceType'], 'Patient')


    def test_clinical(self):
        with app.app.test_client() as c:
            rv = c.get('/api/clinical')
        clinical_data = json.loads(rv.data)
        self.assertTrue('Gleason-score' in clinical_data)
        self.assertEquals(clinical_data['TNM-Condition-stage']['summary'],
                'T1 N0 M0')


if __name__ == '__main__':
    unittest.main()
