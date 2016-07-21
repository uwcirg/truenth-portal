"""Unit test module for Demographics API"""
from flask_webtest import SessionScope
from tests import TestCase, IMAGE_URL, LAST_NAME, FIRST_NAME, TEST_USER_ID
import json

from portal.extensions import db
from portal.models.organization import Organization
from portal.models.role import ROLE


class TestDemographics(TestCase):

    def test_demographicsGET(self):
        self.login()
        rv = self.app.get('/api/demographics')

        fhir = json.loads(rv.data)
        self.assertEquals(len(fhir['identifier']), 2)
        self.assertEquals(fhir['resourceType'], 'Patient')
        self.assertEquals(fhir['name']['family'], LAST_NAME)
        self.assertEquals(fhir['name']['given'], FIRST_NAME)
        self.assertEquals(fhir['photo'][0]['url'], IMAGE_URL)
        # confirm default timezone appears
        tz = [ext for ext in fhir['extension'] if
              ext['url'].endswith('timezone')]
        self.assertEquals('UTC', tz[0]['timezone'])

    def test_demographics404(self):
        self.login()
        self.promote_user(role_name=ROLE.ADMIN)
        rv = self.app.get('/api/demographics/666')
        self.assert404(rv)

    def test_demographicsPUT(self):
        # race / ethnicity require the SLOW addition of concepts to db
        self.add_concepts()

        # clinic reference requires pre-existing organization
        org = Organization(name='test org')
        org2 = Organization(name='another org')
        with SessionScope(db):
            db.session.add(org)
            db.session.add(org2)
            db.session.commit()
        org = db.session.merge(org)
        org2 = db.session.merge(org2)
        org_id, org2_id = org.id, org2.id

        family = 'User'
        given = 'Test'
        dob = '1999-01-31'
        gender = 'Male'
        data = {"name": {"family": family, "given": given},
                "resourceType": "Patient",
                "birthDate": dob,
                "gender": gender,
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
                ],
                "careProvider": [
                    {"reference": "Organization/{}".format(org_id)},
                    {"reference": "api/organization/{}".format(org2_id)},
                ]
               }

        self.login()
        rv = self.app.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        fhir = json.loads(rv.data)
        self.assertEquals(fhir['birthDate'], dob)
        self.assertEquals(fhir['gender'], gender.lower())
        self.assertEquals(fhir['name']['family'], family)
        self.assertEquals(fhir['name']['given'], given)
        self.assertEquals(3, len(fhir['extension']))  # timezone added
        self.assertEquals(2, len(fhir['careProvider']))

        user = db.session.merge(self.test_user)
        self.assertEquals(user.first_name, given)
        self.assertEquals(user.last_name, family)
        self.assertEquals(['2162-6',], [c.code for c in user.ethnicities])
        self.assertEquals(['1096-7',], [c.code for c in user.races])
        self.assertEquals(user.organizations.count(), 2)
        self.assertEquals(user.organizations[0].name, 'test org')
        self.assertEquals(user.organizations[1].name, 'another org')

    def test_demographics_missing_ref(self):
        # reference clinic must exist or expect a 400
        data = {"careProvider": [{"reference": "Organization/1"}],
                "resourceType": "Patient",
               }

        self.login()
        rv = self.app.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assert400(rv)
        self.assertIn('Reference', rv.data)
        self.assertIn('not found', rv.data)

    def test_demographics_duplicate_ref(self):
        # adding duplicate careProvider

        org = Organization(name='test org')
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        org_id = org.id

        # associate test org with test user
        self.test_user.organizations.append(org)
        with SessionScope(db):
            db.session.add(self.test_user)
            db.session.commit()

        data = {"careProvider": [{"reference": "Organization/{}".format(
                org_id)}],
                "resourceType": "Patient",
               }

        self.login()
        rv = self.app.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assert200(rv)
        user = db.session.merge(self.test_user)
        self.assertEquals(user.organizations.count(), 1)
        self.assertEquals(user.organizations[0].name, 'test org')

    def test_demographics_delete_ref(self):
        # existing careProvider should get removed

        org = Organization(name='test org')
        org2 = Organization(name='two')
        org3 = Organization(name='three')
        with SessionScope(db):
            db.session.add(org)
            db.session.add(org2)
            db.session.add(org3)
            db.session.commit()
        org = db.session.merge(org)
        org2 = db.session.merge(org2)
        org3 = db.session.merge(org3)
        org_id = org.id

        # associate test orgs 2 and 3 with test user
        self.test_user.organizations.append(org3)
        self.test_user.organizations.append(org2)
        with SessionScope(db):
            db.session.add(self.test_user)
            db.session.commit()

        # now push only the first org in via the api
        data = {"careProvider": [{"reference": "Organization/{}".format(
                org_id)}],
                "resourceType": "Patient",
               }

        self.login()
        rv = self.app.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assert200(rv)
        user = db.session.merge(self.test_user)

        # confirm only the one sent via API is intact.
        self.assertEquals(user.organizations.count(), 1)
        self.assertEquals(user.organizations[0].name, 'test org')
