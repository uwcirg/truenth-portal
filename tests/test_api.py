"""Unit test module for API"""
import json
from tests import TestCase, LAST_NAME, FIRST_NAME, TEST_USER_ID

from portal.extensions import db
from portal.models.fhir import Observation, UserObservation
from portal.models.fhir import CodeableConcept, ValueQuantity
from portal.models.role import ROLE, STATIC_ROLES
from portal.models.user import User


class TestAPI(TestCase):

    def test_demographicsGET(self):
        self.login()
        rv = self.app.get('/api/demographics')

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

        self.login()
        rv = self.app.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        fhir = json.loads(rv.data)
        self.assertEquals(fhir['birthDate'], dob)
        self.assertEquals(fhir['gender']['coding'][0]['display'], gender)
        self.assertEquals(fhir['name']['family'], family)
        self.assertEquals(fhir['name']['given'], given)


    def test_clinicalGET(self):
        # First push some clinical data into the db for the test user
        observation = Observation()
        observation.codeable_concept = CodeableConcept(
                system='SNOMED-CT', code='372278000',
                display='Gleason score')
        observation.value_quantity = ValueQuantity(value=2)
        db.session.add(observation)
        db.session.flush()
        db.session.add(UserObservation(user_id=int(TEST_USER_ID),
            observation_id=observation.id))
        db.session.commit()

        self.login()
        rv = self.app.get('/api/clinical/%s' % TEST_USER_ID)

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

        self.login()
        rv = self.app.post('/api/clinical/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        fhir = json.loads(rv.data)
        self.assertEquals(fhir['message'], "ok")

    def test_default_role(self):
        self.login()
        rv = self.app.get('/api/roles/{0}'.format(TEST_USER_ID))

        result_roles = json.loads(rv.data)
        self.assertEquals(len(result_roles['roles']), 1)
        self.assertEquals(result_roles['roles'][0]['name'], ROLE.PATIENT)

    def test_unauth_role(self):
        self.login()
        rv = self.app.get('/api/roles/66')

        self.assertEquals(rv.status_code, 401)

    def test_all_roles(self):
        self.login()
        rv = self.app.get('/api/roles')

        result_roles = json.loads(rv.data)
        self.assertEquals(len(result_roles['roles']), len(STATIC_ROLES))

    def test_roles_add(self):
        data = {"roles": [
                {"name": ROLE.APPLICATION_DEVELOPER},
                {"name": ROLE.PATIENT},
                {"name": ROLE.ADMIN}
                ]}

        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.app.put('/api/roles/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assertEquals(rv.status_code, 200)
        doc = json.loads(rv.data)
        self.assertEquals(len(doc['roles']), len(data['roles']))
        user = User.query.get(TEST_USER_ID)
        self.assertEquals(len(user.roles), len(data['roles']))

    def test_roles_delete(self):
        self.promote_user(role_name=ROLE.ADMIN)
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER)
        data = {"roles": [
                {"name": ROLE.PATIENT},
                ]}

        self.login()
        rv = self.app.put('/api/roles/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assertEquals(rv.status_code, 200)
        doc = json.loads(rv.data)
        self.assertEquals(len(doc['roles']), len(data['roles']))
        user = User.query.get(TEST_USER_ID)
        self.assertEquals(len(user.roles), len(data['roles']))

    def test_roles_nochange(self):
        data = {"roles": [
                {"name": ROLE.PATIENT},
                {"name": ROLE.ADMIN}
                ]}

        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.app.put('/api/roles/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assertEquals(rv.status_code, 200)
        doc = json.loads(rv.data)
        self.assertEquals(len(doc['roles']), len(data['roles']))
        user = User.query.get(TEST_USER_ID)
        self.assertEquals(len(user.roles), len(data['roles']))
