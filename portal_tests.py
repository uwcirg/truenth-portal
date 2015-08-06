import json
import os
import tempfile
import unittest

import app

TEST_USER_ID = '5'
FIRST_NAME = 'First'
LAST_NAME = 'Last'

class PortalTestCase(unittest.TestCase):

    def setUp(self):
        app.app.config['TESTING'] = True
        app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'
        app.init_db()
        def create_test_user():
            test_user = app.User(username='testy', id=TEST_USER_ID,
                    first_name=FIRST_NAME, last_name=LAST_NAME)
            app.db.session.add(test_user)
            app.db.session.commit()
        create_test_user()

    def tearDown(self):
        app.db.session.remove()
        app.db.drop_all()

    def test_demographicsGET(self):
        with app.app.test_client() as c:
            with c.session_transaction() as sess:
                sess['id'] = TEST_USER_ID
            rv = c.get('/api/demographics')

        fhir = json.loads(rv.data)
        self.assertEquals(len(fhir['identifier']), 2)
        self.assertEquals(fhir['resourceType'], 'Patient')
        self.assertEquals(fhir['name']['family'], LAST_NAME)
        self.assertEquals(fhir['name']['given'], FIRST_NAME)


    def test_demographicsPUT(self):
        family = 'User'
        given = 'Test'
        dob = '1999-01-31'
        gender = 'Male'
        data = {"name": {"family": family, "given": given},
                "resourceType": "Patient",
                "birthDate": dob,
                "gender": {"coding": [{
                    "code": "M", 
                    "display": gender, 
                    "system": "http://hl7.org/fhir/v3/AdministrativeGender"
                    }]},
                "telecom": [{
                    "system": "phone", 
                    "value": "867-5309"
                    }]}
        with app.app.test_client() as c:
            with c.session_transaction() as sess:
                sess['id'] = TEST_USER_ID
            rv = c.put('/api/demographics/%s' % TEST_USER_ID,
                    content_type='application/json',
                    data=json.dumps(data))

        fhir = json.loads(rv.data)
        self.assertEquals(fhir['birthDate'], dob)
        self.assertEquals(fhir['gender']['coding'][0]['display'], gender)
        self.assertEquals(fhir['name']['family'], family)
        self.assertEquals(fhir['name']['given'], given)


    def test_clinicalGET(self):
        # First push some clinical data into the db for the test user
        observation = app.Observation()
        observation.codeable_concept = app.CodeableConcept(
                system='SNOMED-CT', code='372278000',
                display='Gleason score')
        observation.value_quantity = app.ValueQuantity(value=2)
        app.db.session.add(observation)
        app.db.session.flush()
        app.db.session.add(app.UserObservation(user_id=int(TEST_USER_ID),
            observation_id=observation.id))
        app.db.session.commit()

        with app.app.test_client() as c:
            with c.session_transaction() as sess:
                sess['id'] = TEST_USER_ID
            rv = c.get('/api/clinical/%s' % TEST_USER_ID)

        clinical_data = json.loads(rv.data)
        self.assertEquals('Gleason score',
            clinical_data['entry'][0]['content']['name']['coding'][0]\
                    ['display'])
        self.assertEquals('2',
            clinical_data['entry'][0]['content']['valueQuantity']\
                    ['value'])


    def test_clinicalPOST(self):
        data = {"resourceType": "Observation",
                "name": {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": "28540-3",
                        "display": "Erythrocyte mean corpuscular hemoglobin concentration [Mass/volume]"
                        }]},
                "valueQuantity": {
                    "value": 18.7,
                    "units": "g/dl",
                    "system": "http://unitsofmeasure.org",
                    "code": "g/dl"
                    },
                "status": "final",
                "issued": "2015-08-04T13:27:00+01:00"
                }

        with app.app.test_client() as c:
            with c.session_transaction() as sess:
                sess['id'] = TEST_USER_ID
            rv = c.post('/api/clinical/%s' % TEST_USER_ID,
                    content_type='application/json',
                    data=json.dumps(data))

        fhir = json.loads(rv.data)
        self.assertEquals(fhir['message'], "ok")

if __name__ == '__main__':
    unittest.main()
