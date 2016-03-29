"""Unit test module for API"""
import json
from flask.ext.webtest import SessionScope
from tests import TestCase, IMAGE_URL, LAST_NAME, FIRST_NAME, TEST_USER_ID

from portal.extensions import db
from portal.models.intervention import Intervention, INTERVENTION
from portal.models.fhir import Observation, UserObservation
from portal.models.fhir import Coding, CodeableConcept, ValueQuantity
from portal.models.relationship import Relationship, RELATIONSHIP
from portal.models.role import ROLE, STATIC_ROLES
from portal.models.user import User, UserRelationship


class TestAPI(TestCase):

    def test_portal_wrapper_html(self):
        self.login()
        rv = self.app.get('/api/portal-wrapper-html/')

        self.assertTrue(FIRST_NAME in rv.data)
        self.assertTrue(LAST_NAME in rv.data)

    def test_portal_wrapper_wo_name(self):
        "w/o a users first, last name, username should appear"
        username = 'test2'
        uid = self.add_user(username=username, first_name=None)
        self.login(user_id=uid)
        rv = self.app.get('/api/portal-wrapper-html/')

        self.assertEquals(rv.status_code, 200)
        self.assertTrue(username in rv.data)

    def test_account_creation(self):
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)
        rv = self.app.post('/api/account')

        self.assert200(rv)
        self.assertTrue(rv.json['user_id'] > 0)
        user_id = rv.json['user_id']

        # can we add some demographics and role information
        family = 'User'
        given = 'Test'
        language = 'en-AU'
        coding = {'code': language, 'display': "Australian English",
                  'system': "urn:ietf:bcp:47"}
        data = {"name": {"family": family, "given": given},
                "resourceType": "Patient",
                "communication": [{"language": {"coding": [coding]}}]}
        rv = self.app.put('/api/demographics/{}'.format(user_id),
                content_type='application/json',
                data=json.dumps(data))
        new_user = User.query.get(user_id)
        self.assertEquals(new_user.first_name, given)
        self.assertEquals(new_user.last_name, family)
        self.assertEquals(new_user.username, "{0} {1}".format(given, family))
        self.assertEquals(len(new_user.roles), 0)
        roles = {"roles": [ {"name": ROLE.PATIENT}, ]}
        rv = self.app.put('/api/user/{}/roles'.format(user_id),
                          content_type='application/json',
                          data=json.dumps(roles))
        self.assertEquals(len(new_user.roles), 1)
        self.assertEquals(new_user.locale.codings[0].code, language)

    def test_demographicsGET(self):
        self.login()
        rv = self.app.get('/api/demographics')

        fhir = json.loads(rv.data)
        self.assertEquals(len(fhir['identifier']), 2)
        self.assertEquals(fhir['resourceType'], 'Patient')
        self.assertEquals(fhir['name']['family'], LAST_NAME)
        self.assertEquals(fhir['name']['given'], FIRST_NAME)
        self.assertEquals(fhir['photo'][0]['url'], IMAGE_URL)

    def test_demographicsPUT(self):
        # race / ethnicity require the SLOW addition of concepts to db
        self.add_concepts()

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
                    }],
                "extension": [{
                    "url":
                    "http://hl7.org/fhir/StructureDefinition/us-core-race",
                    "valueCodeableConcept": {
                        "coding": [{
                            "system": "http://hl7.org/fhir/v3/Race",
                            "code": "1096-7"}]}},
                    {"url":
                     "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity",
                     "valueCodeableConcept": {
                         "coding": [{
                             "system": "http://hl7.org/fhir/v3/Ethnicity",
                             "code": "2162-6"}]}}
                ]
               }

        self.login()
        rv = self.app.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        fhir = json.loads(rv.data)
        self.assertEquals(fhir['birthDate'], dob)
        self.assertEquals(fhir['gender']['coding'][0]['display'], gender)
        self.assertEquals(fhir['name']['family'], family)
        self.assertEquals(fhir['name']['given'], given)
        self.assertEquals(2, len(fhir['extension']))

        user = db.session.merge(self.test_user)
        self.assertEquals(user.first_name, given)
        self.assertEquals(user.last_name, family)
        self.assertEquals(['2162-6',], [c.code for c in user.ethnicities])
        self.assertEquals(['1096-7',], [c.code for c in user.races])


    def prep_db_for_clinical(self):
        # First push some clinical data into the db for the test user
        with SessionScope(db):
            observation = Observation()
            coding = Coding(system='SNOMED-CT', code='372278000',
                    display='Gleason score')
            cc = CodeableConcept(codings=[coding,])
            observation.codeable_concept = cc
            observation.value_quantity = ValueQuantity(value=2)
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
                "issued": "2015-08-04T13:27:00+01:00"
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

    def test_intervention_wrong_service_user(self):
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)

        data = {'user_id': TEST_USER_ID, 'access': 'granted'}
        rv = self.app.put('/api/intervention/sexual_recovery',
                content_type='application/json',
                data=json.dumps(data))
        self.assert401(rv)

    def test_intervention(self):
        client = self.add_test_client()
        intervention = Intervention.query.filter_by(
            name=INTERVENTION.SEXUAL_RECOVERY).first()
        client.intervention = intervention
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)

        data = {'user_id': TEST_USER_ID,
                'access': "granted",
                'card_html': "unique HTML set via API"}
        rv = self.app.put('/api/intervention/sexual_recovery',
                content_type='application/json',
                data=json.dumps(data))
        self.assert200(rv)

    def test_default_role(self):
        self.login()
        rv = self.app.get('/api/user/{0}/roles'.format(TEST_USER_ID))

        result_roles = json.loads(rv.data)
        self.assertEquals(len(result_roles['roles']), 1)
        self.assertEquals(result_roles['roles'][0]['name'], ROLE.PATIENT)

    def test_unauth_role(self):
        self.login()
        rv = self.app.get('/api/user/66/roles')

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
        rv = self.app.put('/api/user/%s/roles' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assertEquals(rv.status_code, 200)
        doc = json.loads(rv.data)
        self.assertEquals(len(doc['roles']), len(data['roles']))
        user = User.query.get(TEST_USER_ID)
        self.assertEquals(len(user.roles), len(data['roles']))

    def test_roles_duplicate_add(self):
        data = {"roles": [
                {"name": ROLE.APPLICATION_DEVELOPER},
                ]}

        self.promote_user(role_name=ROLE.ADMIN)
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER)
        self.login()
        rv = self.app.put('/api/user/%s/roles' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assertEquals(rv.status_code, 200)
        doc = json.loads(rv.data)
        self.assertEquals(len(doc['roles']), 3)
        user = User.query.get(TEST_USER_ID)
        self.assertEquals(len(user.roles),  3)

    def test_roles_delete(self):
        self.promote_user(role_name=ROLE.ADMIN)
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER)
        data = {"roles": [
                {"name": ROLE.PATIENT},
                ]}

        self.login()
        rv = self.app.delete('/api/user/%s/roles' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assertEquals(rv.status_code, 200)
        doc = json.loads(rv.data)
        self.assertEquals(len(doc['roles']), 2)
        user = User.query.get(TEST_USER_ID)
        self.assertEquals(len(user.roles), 2)

    def test_roles_nochange(self):
        data = {"roles": [
                {"name": ROLE.PATIENT},
                {"name": ROLE.ADMIN}
                ]}

        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.app.put('/api/user/%s/roles' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assertEquals(rv.status_code, 200)
        doc = json.loads(rv.data)
        self.assertEquals(len(doc['roles']), len(data['roles']))
        user = User.query.get(TEST_USER_ID)
        self.assertEquals(len(user.roles), len(data['roles']))

    def test_all_relationships(self):
        # obtain list of all relationships
        rv = self.app.get('/api/relationships')
        self.assert200(rv)
        self.assertTrue(len(rv.json['relationships']) >= 2)  # we'll add more

    def create_test_relationships(self):
        other_user = self.add_user(username='other')
        partner = Relationship.query.filter_by(name='partner').first()
        rel = UserRelationship(user_id=TEST_USER_ID,
                               relationship_id=partner.id,
                               other_user_id=other_user)
        sponsor = Relationship.query.filter_by(name='sponsor').first()
        rel2 = UserRelationship(user_id=other_user,
                               relationship_id=sponsor.id,
                               other_user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(rel)
            db.session.add(rel2)
            db.session.commit()

    def test_subject_relationships(self):
        # make sure we get relationships for both subject and predicate
        self.create_test_relationships()
        self.login()
        rv = self.app.get('/api/user/{}/relationships'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertTrue(len(rv.json['relationships']) >= 2)  # we'll add more

    def test_set_relationships(self):
        other_user = self.add_user(username='other')
        data = {'relationships':[{'user': TEST_USER_ID,
                                  'has the relationship': 'partner',
                                  'with': other_user},]
               }
        self.login()
        rv = self.app.put('/api/user/{}/relationships'.format(TEST_USER_ID),
                         content_type='application/json',
                         data=json.dumps(data))
        self.assert200(rv)

        ur = UserRelationship.query.filter_by(other_user_id=other_user).first()
        self.assertEquals(ur.relationship.name, RELATIONSHIP.PARTNER)

    def test_delete_relationships(self):
        self.create_test_relationships()
        other_user = User.query.filter_by(username='other').first()
        data = {'relationships':[{'user': TEST_USER_ID,
                                  'has the relationship': 'partner',
                                  'with': other_user.id},]
               }
        self.login()
        rv = self.app.delete('/api/user/{}/relationships'.format(TEST_USER_ID),
                         content_type='application/json',
                         data=json.dumps(data))
        self.assert200(rv)

        # shouldn't find the deleted
        ur = UserRelationship.query.filter_by(
            other_user_id=other_user.id).first()
        self.assertFalse(ur)

        # but the other one should
        ur = UserRelationship.query.filter_by(
            other_user_id=TEST_USER_ID).first()
        self.assertEquals(ur.relationship.name, RELATIONSHIP.SPONSOR)

    def test_delete_relationships_wo_perms(self):
        self.create_test_relationships()
        other_user = User.query.filter_by(username='other').first()
        data = {'relationships':[{'user': other_user.id,
                                  'has the relationship': 'sponsor',
                                  'with': TEST_USER_ID},]
               }
        self.login()
        rv = self.app.delete('/api/user/{}/relationships'.format(TEST_USER_ID),
                         content_type='application/json',
                         data=json.dumps(data))
        self.assert401(rv)

        # should find both relationships intact
        ur = UserRelationship.query.filter_by(
            other_user_id=other_user.id).first()
        self.assertEquals(ur.user_id, TEST_USER_ID)

        ur = UserRelationship.query.filter_by(
            other_user_id=TEST_USER_ID).first()
        self.assertEquals(ur.relationship.name, RELATIONSHIP.SPONSOR)
