"""Unit test module for Clinical API"""
from datetime import datetime, timedelta
from dateutil import parser
from flask import current_app
from flask_webtest import SessionScope
import json
import os
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.fhir import Observation, UserObservation
from portal.models.fhir import Coding, CodeableConcept, ValueQuantity
from portal.models.performer import Performer
from portal.models.reference import Reference
from portal.models.user import User


class TestClinical(TestCase):

    def prep_db_for_clinical(self):
        # First push some clinical data into the db for the test user
        with SessionScope(db):
            audit = Audit(user_id=TEST_USER_ID)
            observation = Observation(audit=audit)
            coding = Coding(system='SNOMED-CT', code='372278000',
                    display='Gleason score')
            cc = CodeableConcept(codings=[coding,])
            observation.codeable_concept = cc
            observation.value_quantity = ValueQuantity(value=2)
            performer = Performer(reference_txt=json.dumps(
                Reference.patient(TEST_USER_ID).as_fhir()))
            observation.performers.append(performer)
            db.session.add(observation)
            db.session.flush()
            db.session.add(UserObservation(user_id=int(TEST_USER_ID),
                observation_id=observation.id))
            db.session.commit()

    def test_clinicalGET(self):
        self.prep_db_for_clinical()
        self.login()
        rv = self.app.get('/api/patient/%s/clinical' % TEST_USER_ID)

        clinical_data = json.loads(rv.data)
        self.assertEquals('Gleason score',
            clinical_data['entry'][0]['content']['code']['coding'][0]\
                    ['display'])
        self.assertEquals('2',
            clinical_data['entry'][0]['content']['valueQuantity']\
                    ['value'])
        self.assertEquals(
            json.dumps(Reference.patient(TEST_USER_ID).as_fhir()),
            clinical_data['entry'][0]['content']['performer'][0])
        self.assertEquals(
            Reference.patient(TEST_USER_ID).as_fhir(),
            clinical_data['entry'][0]['content']['meta']['by'])
        found = parser.parse(
                clinical_data['entry'][0]['content']['meta']['lastUpdated'])
        found = found.replace(tzinfo=None)
        self.assertAlmostEquals(datetime.utcnow(), found,
                                delta= timedelta(seconds=2))
        self.assertEquals(
            current_app.config.metadata.version,
            clinical_data['entry'][0]['content']['meta']['version'])

    def test_clinicalPOST(self):
        data = {"resourceType": "Observation",
                "code": {
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
                "issued": "2015-08-04T13:27:00+01:00",
                "performer": Reference.patient(TEST_USER_ID).as_fhir()
                }

        self.login()
        rv = self.app.post('/api/patient/%s/clinical' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))
        self.assert200(rv)
        fhir = json.loads(rv.data)
        self.assertIn('28540-3', fhir['message'])

    def test_empty_clinical_get(self):
        """Access clinical on user w/o any clinical info"""
        self.login()
        rv = self.app.get('/api/patient/%s/clinical' % TEST_USER_ID)
        self.assert200(rv)

    def test_empty_biopsy_get(self):
        """Access biopsy on user w/o any clinical info"""
        self.login()
        rv = self.app.get('/api/patient/%s/clinical/biopsy' % TEST_USER_ID)
        self.assert200(rv)
        data = json.loads(rv.data)
        self.assertEquals(data['value'], 'unknown')

    def test_clinical_biopsy_put(self):
        """Shortcut API - just biopsy data w/o FHIR overhead"""
        self.login()
        rv = self.app.post('/api/patient/%s/clinical/biopsy' % TEST_USER_ID,
                           content_type='application/json',
                           data=json.dumps({'value': True}))
        self.assert200(rv)
        result = json.loads(rv.data)
        self.assertEquals(result['message'], 'ok')

        # Can we get it back in FHIR?
        rv = self.app.get('/api/patient/%s/clinical' % TEST_USER_ID)
        data = json.loads(rv.data)
        coding = data['entry'][0]['content']['code']['coding'][0] 
        vq = data['entry'][0]['content']['valueQuantity'] 

        self.assertEquals(coding['code'], '111')
        self.assertEquals(coding['display'], 'biopsy')
        self.assertEquals(coding['system'],
                          'http://us.truenth.org/clinical-codes')
        self.assertEquals(vq['value'], 'true')

        # Access the direct biopsy value
        rv = self.app.get('/api/patient/%s/clinical/biopsy' % TEST_USER_ID)
        data = json.loads(rv.data)
        self.assertEquals(data['value'], 'true')

        # Can we alter the value?
        rv = self.app.post('/api/patient/%s/clinical/biopsy' % TEST_USER_ID,
                           content_type='application/json',
                           data=json.dumps({'value': False}))
        self.assert200(rv)
        result = json.loads(rv.data)
        self.assertEquals(result['message'], 'ok')

        # Confirm it's altered
        rv = self.app.get('/api/patient/%s/clinical/biopsy' % TEST_USER_ID)
        data = json.loads(rv.data)
        self.assertEquals(data['value'], 'false')

        # Confirm the db is clean
        user = User.query.get(TEST_USER_ID)
        self.assertEquals(user.observations.count(), 1)

    def test_clinical_pca_diag(self):
        """Shortcut API - just PCa diagnosis w/o FHIR overhead"""
        self.login()
        rv = self.app.post('/api/patient/%s/clinical/pca_diag' % TEST_USER_ID,
                           content_type='application/json',
                           data=json.dumps({'value': True}))
        self.assert200(rv)
        result = json.loads(rv.data)
        self.assertEquals(result['message'], 'ok')

        # Can we get it back in FHIR?
        rv = self.app.get('/api/patient/%s/clinical' % TEST_USER_ID)
        data = json.loads(rv.data)
        coding = data['entry'][0]['content']['code']['coding'][0]
        vq = data['entry'][0]['content']['valueQuantity']

        self.assertEquals(coding['code'], '121')
        self.assertEquals(coding['display'], 'PCa diagnosis')
        self.assertEquals(coding['system'],
                          'http://us.truenth.org/clinical-codes')
        self.assertEquals(vq['value'], 'true')

        # Access the direct pca_diag value
        rv = self.app.get('/api/patient/%s/clinical/pca_diag' % TEST_USER_ID)
        data = json.loads(rv.data)
        self.assertEquals(data['value'], 'true')

    def test_clinical_pca_localized(self):
        """Shortcut API - just PCa localized diagnosis w/o FHIR overhead"""
        self.login()
        rv = self.app.post(
            '/api/patient/%s/clinical/pca_localized' % TEST_USER_ID,
            content_type='application/json', data=json.dumps({'value': True}))
        self.assert200(rv)
        result = json.loads(rv.data)
        self.assertEquals(result['message'], 'ok')

        # Can we get it back in FHIR?
        rv = self.app.get('/api/patient/%s/clinical' % TEST_USER_ID)
        data = json.loads(rv.data)
        coding = data['entry'][0]['content']['code']['coding'][0]
        vq = data['entry'][0]['content']['valueQuantity']

        self.assertEquals(coding['code'], '141')
        self.assertEquals(coding['display'], 'PCa localized diagnosis')
        self.assertEquals(coding['system'],
                          'http://us.truenth.org/clinical-codes')
        self.assertEquals(vq['value'], 'true')

        # Access the direct pca_localized value
        rv = self.app.get(
            '/api/patient/%s/clinical/pca_localized' % TEST_USER_ID)
        data = json.loads(rv.data)
        self.assertEquals(data['value'], 'true')

    def test_clinical_tx(self):
        """Shortcut API - just treatment w/o FHIR overhead"""
        self.login()
        rv = self.app.post('/api/patient/%s/clinical/tx' % TEST_USER_ID,
                           content_type='application/json',
                           data=json.dumps({'value': True}))
        self.assert200(rv)
        result = json.loads(rv.data)
        self.assertEquals(result['message'], 'ok')

        # Can we get it back in FHIR?
        rv = self.app.get('/api/patient/%s/clinical' % TEST_USER_ID)
        data = json.loads(rv.data)
        coding = data['entry'][0]['content']['code']['coding'][0] 
        vq = data['entry'][0]['content']['valueQuantity'] 

        self.assertEquals(coding['code'], '131')
        self.assertEquals(coding['display'], 'treatment begun')
        self.assertEquals(coding['system'],
                          'http://us.truenth.org/clinical-codes')
        self.assertEquals(vq['value'], 'true')

        # Access the direct tx api
        rv = self.app.get('/api/patient/%s/clinical/tx' % TEST_USER_ID)
        data = json.loads(rv.data)
        self.assertEquals(data['value'], 'true')

    def test_weight(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'weight_example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        self.login()
        rv = self.app.put('/api/patient/{}/clinical'.format(TEST_USER_ID),
                         content_type='application/json',
                         data=json.dumps(data))
        self.assert200(rv)

        obs = self.test_user.observations.one()  # only expect the one
        self.assertEquals('185', obs.value_quantity.value)
        self.assertEquals(3, len(obs.codeable_concept.codings))
