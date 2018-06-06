"""Unit test module for Demographics API"""
import json

from flask_webtest import SessionScope
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.auth import AuthProvider
from portal.models.identifier import Identifier
from portal.models.organization import Organization, OrgTree
from portal.models.reference import Reference
from portal.models.role import ROLE
from portal.models.user import User
from portal.system_uri import US_NPI
from tests import (
    FIRST_NAME,
    IMAGE_URL,
    LAST_NAME,
    TEST_USER_ID,
    TEST_USERNAME,
    TestCase,
)


class TestDemographics(TestCase):

    def test_demographicsGET(self):
        self.login()
        rv = self.client.get('/api/demographics')

        fhir = json.loads(rv.data)
        self.assertEqual(len(fhir['identifier']), 2)
        self.assertEqual(fhir['resourceType'], 'Patient')
        self.assertEqual(fhir['name']['family'], LAST_NAME)
        self.assertEqual(fhir['name']['given'], FIRST_NAME)
        self.assertEqual(fhir['photo'][0]['url'], IMAGE_URL)
        # confirm default timezone appears
        tz = [ext for ext in fhir['extension'] if
              ext['url'].endswith('timezone')]
        self.assertEqual('UTC', tz[0]['timezone'])
        self.assertEqual(False, fhir['deceasedBoolean'])

        # confirm empties aren't present in extension; i.e. only 'url' key
        self.assertFalse([e for e in fhir['extension'] if len(e.keys()) == 1])
        self.assertEqual(len(fhir['telecom']), 1)
        self.assertTrue(fhir['telecom'][0]['value'], TEST_USERNAME)

    def test_demographics404(self):
        self.login()
        self.promote_user(role_name=ROLE.ADMIN)
        rv = self.client.get('/api/demographics/666')
        self.assert404(rv)

    def test_demographicsPUT(self):
        # race / ethnicity require the SLOW addition of concepts to db
        self.add_concepts()

        # clinic reference requires pre-existing organization
        self.shallow_org_tree()
        (org_id, org_name), (org2_id, org2_name) = [
            (org.id, org.name) for org in Organization.query.filter(
                Organization.id > 0).limit(2)]

        pract = self.add_practitioner(first_name='Indiana', last_name='Jones')
        pract_id = pract.id

        family = 'User'
        given = 'Test'
        dob = '1999-01-31'
        dod = '2027-12-31T09:10:00+00:00'
        gender = 'Male'
        phone = "867-5309"
        alt_phone = "555-5555"
        data = {"name": {"family": family, "given": given},
                "resourceType": "Patient",
                "birthDate": dob,
                "deceasedDateTime": dod,
                "gender": gender,
                "telecom": [
                    {
                        "system": "phone",
                        "use": "mobile",
                        "value": phone,
                    }, {
                        "system": "phone",
                        "use": "home",
                        "value": alt_phone,
                    }, {
                        "system": 'email',
                        'value': '__no_email__'
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
                    {"reference": "Practitioner/{}".format(pract_id)},
                ]
               }

        self.login()
        rv = self.client.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assert200(rv)
        fhir = json.loads(rv.data)
        for item in fhir['telecom']:
            if item['system'] == 'phone':
                if item['use'] == 'home':
                    self.assertEqual(alt_phone, item['value'])
                elif item['use'] == 'mobile':
                    self.assertEqual(phone, item['value'])
                else:
                    self.fail(
                        'unexpected telecom use: {}'.format(item['use']))
            else:
                self.fail(
                    'unexpected telecom system: {}'.format(item['system']))
        self.assertEqual(fhir['birthDate'], dob)
        self.assertEqual(fhir['deceasedDateTime'], dod)
        self.assertEqual(fhir['gender'], gender.lower())
        self.assertEqual(fhir['name']['family'], family)
        self.assertEqual(fhir['name']['given'], given)
        # ignore added timezone and empty extensions
        self.assertEqual(2, len(
            [ext for ext in fhir['extension']
             if 'valueCodeableConcept' in ext]))
        self.assertEqual(3, len(fhir['careProvider']))
        self.assertTrue(Reference.practitioner(pract_id).as_fhir() in fhir['careProvider'])

        user = db.session.merge(self.test_user)
        self.assertTrue(user._email.startswith('__no_email__'))
        self.assertTrue(user.email is None)
        self.assertEqual(user.first_name, given)
        self.assertEqual(user.last_name, family)
        self.assertEqual(['2162-6'], [c.code for c in user.ethnicities])
        self.assertEqual(['1096-7'], [c.code for c in user.races])
        self.assertEqual(user.organizations.count(), 2)
        self.assertEqual(user.organizations[0].name, org_name)
        self.assertEqual(user.organizations[1].name, org2_name)
        self.assertEqual(user.practitioner_id, pract_id)

    def test_auth_identifiers(self):
        # add a fake FB and Google auth provider for user
        ap_fb = AuthProvider(provider='facebook', provider_id='fb-123',
                             user_id=TEST_USER_ID)
        ap_g = AuthProvider(provider='google', provider_id='google-123',
                             user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(ap_fb)
            db.session.add(ap_g)
            db.session.commit()
        self.login()
        rv = self.client.get('/api/demographics')

        fhir = json.loads(rv.data)
        self.assertEqual(len(fhir['identifier']), 4)

        # put a study identifier
        study_id = {
            "system":"http://us.truenth.org/identity-codes/external-study-id",
            "use":"secondary","value":"Test Study Id"}
        fhir['identifier'].append(study_id)
        rv = self.client.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(fhir))
        user = User.query.get(TEST_USER_ID)
        self.assertEqual(len(user.identifiers), 5)

    def test_bogus_identifiers(self):
        # empty string values causing problems - prevent insertion
        self.login()
        rv = self.client.get('/api/demographics')

        fhir = json.loads(rv.data)
        self.assertEqual(len(fhir['identifier']), 2)

        # put a study identifier
        study_id = {
            "system": "http://us.truenth.org/identity-codes/external-study-id",
            "use": "secondary", "value": ""}
        fhir['identifier'].append(study_id)
        rv = self.client.put(
            '/api/demographics/%s' % TEST_USER_ID,
            content_type='application/json',
            data=json.dumps(fhir))
        self.assert400(rv)
        user = User.query.get(TEST_USER_ID)
        self.assertEqual(len(user.identifiers), 2)

    def test_demographics_update_email(self):
        data = {"resourceType": "Patient",
                "telecom": [
                    {
                        "system": 'email',
                        'value': 'updated@email.com'
                    }],
               }

        self.login()
        rv = self.client.put(
            '/api/demographics/%s' % TEST_USER_ID,
            content_type='application/json', data=json.dumps(data))
        self.assert200(rv)
        user = User.query.get(TEST_USER_ID)
        self.assertEqual(user.email, 'updated@email.com')

    def test_demographics_bad_dob(self):
        data = {"resourceType": "Patient",
                "birthDate": '10/20/1980'
               }

        self.login()
        rv = self.client.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))
        self.assert400(rv)

    def test_demographics_list_names(self):
        # confirm we can handle when given lists for names as spec'd
        data = {
            "resourceType": "Patient",
            "name": [
                {"family": ['family'], "given": ['given']}
            ]}

        self.login()
        rv = self.client.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))
        self.assert200(rv)
        user = User.query.get(TEST_USER_ID)
        self.assertEqual(user.last_name, 'family')
        self.assertEqual(user.first_name, 'given')

    def test_demographics_missing_ref(self):
        # reference clinic must exist or expect a 400
        data = {"careProvider": [{"reference": "Organization/1"}],
                "resourceType": "Patient",
               }

        self.login()
        rv = self.client.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assert400(rv)
        self.assertIn('Reference', rv.data)
        self.assertIn('not found', rv.data)

    def test_demographics_duplicate_ref(self):
        # adding duplicate careProvider

        self.shallow_org_tree()
        org = Organization.query.filter(Organization.id > 0).first()
        org_id, org_name = org.id, org.name

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
        rv = self.client.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assert200(rv)
        user = db.session.merge(self.test_user)
        self.assertEqual(user.organizations.count(), 1)
        self.assertEqual(user.organizations[0].name, org_name)

    def test_demographics_delete_ref(self):
        # existing careProvider should get removed
        self.login()

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

        rv = self.client.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assert200(rv)
        user = db.session.merge(self.test_user)

        # confirm only the one sent via API is intact.
        self.assertEqual(user.organizations.count(), 1)
        self.assertEqual(user.organizations[0].name, 'test org')

    def test_demographics_identifier_ref(self):
        # referencing careProvider by (unique) external Identifier

        self.shallow_org_tree()
        org = Organization.query.filter(Organization.id > 0).first()
        org_id, org_name = org.id, org.name

        # create OrganizationIdentifier and add to org
        org_id_system = "testsystem"
        org_id_value = "testval"
        ident = Identifier(id=99, system=org_id_system, value=org_id_value)
        org.identifiers.append(ident)
        with SessionScope(db):
            db.session.commit()

        # create Practitioner and add Identifier
        pract = self.add_practitioner(
            first_name="Indiana", last_name="Jones", id_value='practval')

        data = {"careProvider": [
                    {"reference": "Organization/{}?system={}".format(
                        org_id_value, org_id_system)},
                    {"reference": "Practitioner/{}?system={}".format(
                        'practval', US_NPI)}
                ],
                "resourceType": "Patient",
               }

        self.login()
        rv = self.client.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assert200(rv)
        user, pract = map(db.session.merge, (self.test_user, pract))
        self.assertEqual(user.organizations.count(), 1)
        self.assertEqual(user.organizations[0].name, org_name)
        self.assertEqual(user.practitioner_id, pract.id)

    def test_non_admin_org_change(self):
        """non-admin staff can't change their top-level orgs"""
        self.bless_with_basics()
        self.promote_user(role_name=ROLE.STAFF)
        self.test_user = db.session.merge(self.test_user)

        top = OrgTree().find(
            self.test_user.organizations.first().id).top_level()

        # Attempt to add the top-level org should raise
        self.login()
        data = {"careProvider": [{"reference": "Organization/{}".format(
                top)}],
                "resourceType": "Patient",
               }

        rv = self.client.put(
            '/api/demographics/%s' % TEST_USER_ID,
            content_type='application/json',
            data=json.dumps(data))
        self.assert400(rv)

    def test_alt_phone_removal(self):
        user = User.query.get(TEST_USER_ID)
        user.phone = '111-1111'
        user.alt_phone = '555-5555'
        with SessionScope(db):
            db.session.add(user)
            db.session.commit()

        data = {"resourceType": "Patient",
                "telecom": [
                    {
                        "system": "phone",
                        "value": '867-5309',
                    }, {
                        "system": 'email',
                        'value': '__no_email__'
                    }]
               }

        self.login()
        rv = self.client.put('/api/demographics/%s' % TEST_USER_ID,
                content_type='application/json',
                data=json.dumps(data))

        self.assert200(rv)
        fhir = json.loads(rv.data)
        for item in fhir['telecom']:
            if item['system'] == 'phone':
                if item['use'] == 'mobile':
                    self.assertEqual(item['value'], '867-5309')
                elif item['use'] == 'home':
                    self.assertEqual(item['value'], None)
                else:
                    self.fail(
                        'unexpected telecom use: {}'.format(item['use']))
            else:
                self.fail(
                    'unexpected telecom system: {}'.format(item['system']))

    def test_deceased_undead(self):
        "Confirm we can remove time of death via deceasedBoolean: False"
        self.promote_user(role_name=ROLE.PATIENT)
        d_audit = Audit(
            user_id=TEST_USER_ID, subject_id=TEST_USER_ID, context='user',
            comment="time of death for user {}".format(TEST_USER_ID))
        with SessionScope(db):
            db.session.add(d_audit)
            db.session.commit()
        self.test_user, d_audit = map(db.session.merge, (self.test_user, d_audit))
        self.test_user.deceased = d_audit
        self.login()
        data = {"resourceType": "Patient",
                'deceasedBoolean': False}
        rv = self.client.put(
            '/api/demographics/%s' % TEST_USER_ID,
            content_type='application/json',
            data=json.dumps(data))
        self.assertTrue(rv.status_code, 200)
        patient = User.query.get(TEST_USER_ID)
        self.assertFalse(patient.deceased)
