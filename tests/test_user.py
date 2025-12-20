"""Unit test module for user model and views"""


from datetime import datetime
import json
import re
import urllib
import urllib.parse

from flask_webtest import SessionScope
import pytest
from sqlalchemy import and_
from werkzeug.exceptions import (
    BadRequest,
    HTTPException,
    NotFound,
    Unauthorized,
)

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.auth import AuthProvider
from portal.models.codeable_concept import CodeableConcept
from portal.models.coding import Coding
from portal.models.encounter import Encounter
from portal.models.message import EmailMessage
from portal.models.observation import Observation
from portal.models.organization import Organization, OrganizationLocale
from portal.models.performer import Performer
from portal.models.reference import Reference
from portal.models.relationship import RELATIONSHIP, Relationship
from portal.models.role import ROLE, STATIC_ROLES
from portal.models.user import (
    TimezoneExtension,
    User,
    UserEthnicity,
    UserEthnicityExtension,
    UserIndigenous,
    UserIndigenousStatusExtension,
    UserObservation,
    UserRelationship,
    get_user,
    permanently_delete_user,
    user_extension_map,
)
from portal.models.user_consent import STAFF_EDITABLE_MASK, UserConsent
from portal.models.value_quantity import ValueQuantity
from portal.system_uri import (
    TRUENTH_EXTENSTION_NHHD_291036,
    TRUENTH_USERNAME,
    TRUENTH_VALUESET_NHHD_291036,
)
from tests import TEST_USER_ID, TEST_USERNAME, TestCase


def test_null_id():
    with pytest.raises(BadRequest):
        get_user(None, 'view')


def test_empty_id():
    with pytest.raises(NotFound):
        get_user('', 'view')


class TestUser(TestCase):
    """User model and view tests"""

    def test_unique_email(self):
        self.login()

        # bad email param should raise 400
        response = self.client.get('/api/unique_email?email=h2@1')
        assert response.status_code == 400

        email = 'John+Test@example.com'
        request = '/api/unique_email?email={}'.format(urllib.parse.quote(
            email))
        response = self.client.get(request)
        assert response.status_code == 200
        results = response.json
        assert results['unique'] is True

        # should still be unique if it's the current user's email
        # test also the case insensitive match on user's email
        self.test_user.email = email.upper()
        with SessionScope(db):
            db.session.commit()
        response = self.client.get(request)
        assert response.status_code == 200
        results = response.json
        assert results['unique'] is True

        # but a second user should see false
        second = self.add_user(username='second@foo.com')
        self.login(second.id)
        response = self.client.get(request)
        assert response.status_code == 200
        results = response.json
        assert results['unique'] is False

        # admins can test for other users
        request = '/api/unique_email?email={}&user_id={}'.format(
            urllib.parse.quote(email), TEST_USER_ID)
        self.promote_user(second, ROLE.ADMIN.value)
        response = self.client.get(request)
        assert response.status_code == 200
        results = response.json
        assert results['unique'] is True

    def test_unique_hidden_email(self):
        # hidden emails, such as masked invited user create collisions
        email = 'fake@email.com'
        fake_user = self.add_user(username=email)
        fake_user.mask_email()

        self.login()
        request = '/api/unique_email?email={}'.format(urllib.parse.quote(
            email))
        response = self.client.get(request)
        assert response.status_code == 200
        assert response.json['unique'] is False

    def test_unique_email_when_more_than_one_match_exists(self):
        self.login()

        # If there are more than two emails that match
        # we should see false
        # This scenario should not happen, but when it does
        # we should fail gracefully
        email = 'example@gmail.com'
        firstMatch = self.add_user(username='foo', email=email)
        secondMatch = self.add_user(username='bar', email=email.upper())
        response = self.client.get(
            '/api/unique_email',
            query_string={'email': email}
        )
        assert response.status_code == 200
        results = response.json
        assert results['unique'] is False

    def test_unique_email_with_dashes_replaced_by_underscores(self):
        self.login()

        # Emails with dashes are found when searching for
        # the same email replaced with underscores
        # These are diferent emails so no results should be found
        # https://jira.movember.com/browse/TN-1472?filter=-1
        email = 'example-@gmail.com'
        email_with_underscore = email.replace('-', '_')
        self.add_user(username='foo', email=email)
        response = self.client.get(
            '/api/unique_email',
            query_string={'email': email_with_underscore}
        )
        assert response.status_code == 200
        results = response.json
        assert results['unique'] is True

    def test_ethnicities(self):
        """Apply a few ethnicities via FHIR

        Breaking with the "unit" philosophy, as it takes so long to load
        the concepts - several tests done concurrently here.

        """
        # Load the SLOW to load concepts as needed here
        self.add_concepts()

        # Add two ethnicities directly - one in and one not in extension below
        concepts = Coding.query.filter(Coding.code.in_(
            ('2142-8', '2135-2'))).all()
        with SessionScope(db):
            db.session.add(UserEthnicity(user_id=TEST_USER_ID,
                                         coding_id=concepts[0].id))
            db.session.add(UserEthnicity(user_id=TEST_USER_ID,
                                         coding_id=concepts[1].id))
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.ethnicities.count() == 2

        extension = {
            "url": "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity"}
        kls = user_extension_map(user=self.test_user, extension=extension)
        assert isinstance(kls, UserEthnicityExtension)

        # generate FHIR from user's ethnicities
        fhir_data = kls.as_fhir()

        assert len(fhir_data['valueCodeableConcept']['coding']) == 2
        codes = [
            c['code'] for c in fhir_data['valueCodeableConcept']['coding']]
        assert '2135-2' in codes
        assert '2142-8' in codes

        # now create a new extension (FHIR like) and apply to the user
        extension = {
            "url": "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity",
            "valueCodeableConcept": {
                 "coding": [
                     {"system": "http://hl7.org/fhir/v3/Ethnicity",
                      "code": "2162-6"
                      },
                     {"system": "http://hl7.org/fhir/v3/Ethnicity",
                      "code": "2142-8"}, ]}}

        ue = UserEthnicityExtension(self.test_user, extension)
        ue.apply_fhir()
        assert self.test_user.ethnicities.count() == 2
        found = [c.code for c in self.test_user.ethnicities]
        assert '2162-6' in found
        assert '2142-8' in found

    def test_australian_indigenous_status(self):
        """Apply a few indigenous via FHIR from the NHHD_291036 value set"""

        # Add two indigenous directly - one in and one not in extension below
        concepts = Coding.query.filter(
            and_(Coding.code.in_(('1', '4')),
                 Coding.system == TRUENTH_VALUESET_NHHD_291036)).all()
        with SessionScope(db):
            db.session.add(UserIndigenous(
                user_id=TEST_USER_ID, coding_id=concepts[0].id))
            db.session.add(UserIndigenous(
                user_id=TEST_USER_ID, coding_id=concepts[1].id))
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.indigenous.count() == 2

        extension = {"url": TRUENTH_EXTENSTION_NHHD_291036}
        kls = user_extension_map(user=self.test_user, extension=extension)
        assert isinstance(kls, UserIndigenousStatusExtension)

        # generate FHIR from user's ethnicities
        fhir_data = kls.as_fhir()

        assert len(fhir_data['valueCodeableConcept']['coding']) == 2
        codes = [
            c['code'] for c in fhir_data['valueCodeableConcept']['coding']]
        assert '1' in codes
        assert '4' in codes

        # now create a new extension (FHIR like) and apply to the user
        extension = {
            "url": TRUENTH_EXTENSTION_NHHD_291036,
            "valueCodeableConcept": {
                "coding": [
                    {"system": TRUENTH_VALUESET_NHHD_291036,
                     "code": "1"
                     },
                    {"system": TRUENTH_VALUESET_NHHD_291036,
                     "code": "9"
                     },
                ]
            }}

        ue = UserIndigenousStatusExtension(self.test_user, extension)
        ue.apply_fhir()
        assert self.test_user.indigenous.count() == 2
        found = [c.code for c in self.test_user.indigenous]
        assert '1' in found
        assert '9' in found

    def test_delete_user(self):
        actor = self.add_user('actor')
        user, actor = map(db.session.merge, (self.test_user, actor))
        user_id, actor_id = user.id, actor.id
        self.promote_user(user=actor, role_name=ROLE.ADMIN.value)
        self.login(user_id=actor_id)
        response = self.client.delete('/api/user/{}'.format(user_id))
        assert response.status_code == 200
        user = db.session.merge(user)
        assert user.deleted_id
        assert user._email.startswith("__deleted_")
        assert user.email == TEST_USERNAME
        ids = [id for id in user.identifiers if id.system == TRUENTH_USERNAME]
        assert ids[0].value.startswith("__deleted_")

    def test_delete_lock(self):
        """changing attributes on a deleted user should raise"""
        actor = self.add_user('actor')
        user, actor = map(db.session.merge, (self.test_user, actor))
        user.delete_user(acting_user=actor)

        with pytest.raises(ValueError):
            user.first_name = 'DontDoIt'

    def test_permanently_delete_user(self):
        # created acting user and to-be-deleted user
        actor = self.add_user('actor')
        deleted = self.add_user('deleted')
        deleted, actor = map(db.session.merge, (deleted, actor))
        deleted_id, actor_id = deleted.id, actor.id
        deleted_email, actor_email = deleted.email, actor.email
        self.promote_user(user=actor, role_name=ROLE.ADMIN.value)
        with SessionScope(db):
            db.session.commit()
        deleted = db.session.merge(deleted)

        # create observation and user_observation
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        observation = Observation()
        coding = Coding(system='SNOMED-CT', code='372278000',
                        display='Gleason score')
        cc = CodeableConcept(codings=[coding, ])
        observation.codeable_concept = cc
        observation.value_quantity = ValueQuantity(value=2)
        performer = Performer(reference_txt=json.dumps(
            Reference.patient(TEST_USER_ID).as_fhir()))
        observation.performers.append(performer)
        enc = Encounter(status='planned', auth_method='url_authenticated',
                        user_id=TEST_USER_ID, start_time=datetime.utcnow())
        with SessionScope(db):
            db.session.add(observation)
            db.session.add(enc)
            db.session.commit()
        observation, enc = map(db.session.merge, (observation, enc))
        observation_id, enc_id = observation.id, enc.id
        user_obs = UserObservation(user_id=deleted_id, audit=audit,
                                   observation_id=observation_id,
                                   encounter_id=enc_id)
        with SessionScope(db):
            db.session.add(user_obs)
            db.session.commit()
        user_obs = db.session.merge(user_obs)
        user_obs_id = user_obs.id

        # create user and subject audits
        subj_audit = Audit(user_id=TEST_USER_ID, subject_id=deleted_id)
        user_audit = Audit(user_id=deleted_id, subject_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(subj_audit)
            db.session.add(user_audit)
            db.session.commit()
        subj_audit, user_audit = map(db.session.merge,
                                     (subj_audit, user_audit))
        subj_audit_id, user_audit_id = subj_audit.id, user_audit.id

        # create user_consent and audit
        consent_org = Organization(name='test org')
        consent_audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(consent_org)
            db.session.add(consent_audit)
            db.session.commit()
            db.session.add(UserConsent(
                user_id=deleted_id,
                organization_id=consent_org.id,
                audit=consent_audit,
                agreement_url='http://example.org',
                research_study_id=0,
                options=STAFF_EDITABLE_MASK))
            db.session.commit()
        consent_org, consent_audit = map(db.session.merge,
                                         (consent_org, consent_audit))
        co_id, ca_id = consent_org.id, consent_audit.id

        # permanently deleted user, check deletion cascades
        permanently_delete_user(deleted_email, actor=actor_email)
        assert not User.query.get(deleted_id)
        assert not UserObservation.query.get(user_obs_id)
        assert Observation.query.get(observation_id)
        assert not Audit.query.get(subj_audit_id)
        assert not Audit.query.get(user_audit_id)
        assert not UserConsent.query.get(co_id)
        assert not Audit.query.get(ca_id)

    def test_reactivate_user(self):
        actor = self.add_user('actor')
        user, actor = map(db.session.merge, (self.test_user, actor))
        user_id, actor_id = user.id, actor.id
        self.promote_user(user=actor, role_name=ROLE.ADMIN.value)
        self.login(user_id=actor_id)
        response = self.client.delete('/api/user/{}'.format(user_id))
        assert response.status_code == 200
        user = db.session.merge(user)
        assert user.deleted_id
        assert user._email.startswith("__deleted_")
        assert user.email == TEST_USERNAME
        ids = [id for id in user.identifiers if id.system == TRUENTH_USERNAME]
        assert ids[0].value.startswith("__deleted_")

        # Now bring back to life
        response = self.client.post('/api/user/{}/reactivate'.format(user_id))
        assert response.status_code == 200
        user = db.session.merge(user)
        assert user.deleted_id is None
        assert user._email == TEST_USERNAME
        assert user.active is True

        # Second POST should fail
        response = self.client.post('/api/user/{}/reactivate'.format(user_id))
        assert response.status_code == 400

    def test_user_encounter(self):
        self.login()
        response = self.client.get(
            '/api/user/{}/encounter'.format(TEST_USER_ID))
        assert response.status_code == 200
        assert response.json['auth_method'] == 'password_authenticated'

    def test_user_timezone(self):
        assert self.test_user.timezone == 'UTC'
        self.login()
        # Set to bogus, confirm exception
        data = {"resourceType": "Patient",
                "extension": [{"url": TimezoneExtension.extension_url,
                               "timezone": "bogus"}]}
        response = self.client.put(
            '/api/demographics/{}'.format(TEST_USER_ID),
            content_type='application/json', data=json.dumps(data))
        assert response.status_code == 400

        # Valid setting should work
        data['extension'][0]['timezone'] = 'US/Eastern'
        response = self.client.put(
            '/api/demographics/{}'.format(TEST_USER_ID),
            content_type='application/json', data=json.dumps(data))
        assert response.status_code == 200
        user = User.query.get(TEST_USER_ID)
        assert user.timezone == 'US/Eastern'

    def test_ur_format(self):
        ur = UserRelationship(user_id=TEST_USER_ID, other_user_id=TEST_USER_ID,
                              relationship_id=1)
        db.session.add(ur)
        db.session.commit()
        ur_str = "test format {}".format(ur)
        assert 'Relationship' in ur_str

    def test_account_creation_with_null_org(self):
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)
        data = {'organizations': [{'organization_id': None}]}
        response = self.client.post(
            '/api/account', data=json.dumps(data),
            content_type='application/json')
        assert response.status_code == 400

    def test_account_creation(self):
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)
        response = self.client.post('/api/account')

        assert response.status_code == 200
        assert response.json['user_id'] > 0
        user_id = response.json['user_id']

        # can we add some demographics and role information
        family = 'User'
        given = 'Test'
        language = 'en_AU'
        language_name = "Australian English"
        coding = {'code': language, 'display': language_name,
                  'system': "urn:ietf:bcp:47"}
        data = {"name": {"family": family, "given": given},
                "resourceType": "Patient",
                "communication": [{"language": {"coding": [coding]}}]}
        response = self.client.put(
            '/api/demographics/{}'.format(user_id),
            content_type='application/json', data=json.dumps(data))
        new_user = User.query.get(user_id)
        assert new_user.first_name == given
        assert new_user.last_name == family
        assert new_user.username is None
        assert len(new_user.roles) == 0
        roles = {"roles": [{"name": ROLE.PATIENT.value}]}
        response = self.client.put(
            '/api/user/{}/roles'.format(user_id),
            content_type='application/json', data=json.dumps(roles))
        assert len(new_user.roles) == 1
        assert new_user.locale_code == language
        assert new_user.locale_name == language_name

    def test_tz_set_on_account_creation(self):
        org = Organization(id=101, name='org', timezone='US/Pacific')
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()

        data = {
            'organizations': [{'organization_id': 101}],
            'consents': [{'organization_id': 101,
                          'agreement_url': 'http://fake.org',
                          'staff_editable': True,
                          'send_reminders': False}],
            'roles': [{'name': ROLE.PATIENT.value}]}

        service_user = self.add_service_user()
        self.login(user_id=service_user.id)

        response = self.client.post(
            '/api/account', content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200

        user_id = response.json['user_id']
        new_user = User.query.get(user_id)
        assert new_user.timezone == 'US/Pacific'

    def test_account_creation_by_staff(self):
        # permission challenges when done as staff
        self.shallow_org_tree()
        org, org2 = [org for org in Organization.query.filter(
            Organization.id > 0).limit(2)]
        org_id, org2_id = org.id, org2.id
        staff = self.add_user('provider@example.com')
        staff.organizations.append(org)
        staff.organizations.append(org2)
        staff_id = staff.id
        self.promote_user(user=staff, role_name=ROLE.STAFF.value)
        data = {
            'organizations': [
                {'organization_id': org_id},
                {'organization_id': org2_id}],
            'consents': [{
                'organization_id': org_id,
                'agreement_url': 'http://fake.org',
                'staff_editable': True,
                'send_reminders': False}],
            'roles': [{'name': ROLE.PATIENT.value}],
        }
        self.login(user_id=staff_id)
        response = self.client.post(
            '/api/account', content_type='application/json',
            data=json.dumps(data))

        assert response.status_code == 200
        assert response.json['user_id'] > 0
        user_id = response.json['user_id']

        # can we add some demographics and role information
        family = 'User'
        given = 'Test'
        language = 'en_AU'
        language_name = "Australian English"
        coding = {'code': language, 'display': language_name,
                  'system': "urn:ietf:bcp:47"}
        data = {"name": {"family": family, "given": given},
                "resourceType": "Patient",
                "communication": [{"language": {"coding": [coding]}}]}
        response = self.client.put(
            '/api/demographics/{}'.format(user_id),
            content_type='application/json', data=json.dumps(data))
        assert response.status_code == 200
        new_user = User.query.get(user_id)
        assert new_user.first_name == given
        assert new_user.last_name == family
        assert new_user.username is None
        assert len(new_user.roles) == 1
        roles = {"roles": [{"name": ROLE.PATIENT.value}]}
        response = self.client.put(
            '/api/user/{}/roles'.format(user_id),
            content_type='application/json', data=json.dumps(roles))
        assert len(new_user.roles) == 1
        assert new_user.locale_code == language
        assert new_user.locale_name == language_name
        assert len(new_user.organizations) == 2

    def test_failed_account_creation_by_staff(self):
        # without the right set of consents & roles, should fail
        self.shallow_org_tree()
        org, org2 = [org for org in Organization.query.filter(
            Organization.id > 0).limit(2)]
        org_id, org2_id = org.id, org2.id
        staff = self.add_user('provider@example.com')
        staff.organizations.append(org)
        staff.organizations.append(org2)
        staff_id = staff.id
        self.promote_user(user=staff, role_name=ROLE.STAFF.value)
        data = {
            'organizations': [{'organization_id': org_id},
                              {'organization_id': org2_id}],
            'consents': [{'organization_id': org_id,
                          'agreement_url': 'http://fake.org',
                          'staff_editable': True,
                          'send_reminders': False}],
            'roles': [{'name': ROLE.PARTNER.value}],
        }
        self.login(user_id=staff_id)
        response = self.client.post(
            '/api/account', content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 400

    def test_user_by_organization(self):
        # generate a handful of users in different orgs
        org_evens = Organization(name='odds')
        org_odds = Organization(name='odds')
        with SessionScope(db):
            map(db.session.add, (org_evens, org_odds))

            for i in range(5):
                user = self.add_user(username='test_user{}@foo.com'.format(i))
                if i % 2:
                    user.organizations.append(org_odds)
                else:
                    user.organizations.append(org_evens)
                db.session.add(user)

            db.session.commit()
        org_evens, org_odds = map(db.session.merge, (org_evens, org_odds))

        evens = org_evens.users
        odds = org_odds.users
        assert len(evens) == 3
        assert len(odds) == 2
        pattern = re.compile(r'test_user(\d+)@foo.com')
        assert all([int(pattern.match(o.username).groups()[0])
                    % 2 for o in odds])

    def test_default_role(self):
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.promote_user(role_name=ROLE.STAFF.value)
        self.login()
        response = self.client.get('/api/user/{0}/roles'.format(TEST_USER_ID))

        result_roles = response.json
        assert len(result_roles['roles']) == 2
        received = [r['name'] for r in result_roles['roles']]
        assert ROLE.PATIENT.value in received
        assert ROLE.STAFF.value in received
        display_names = [r['display_name'] for r in result_roles['roles']]
        assert 'Patient' in display_names
        assert 'Staff' in display_names

    def test_unauth_role(self):
        self.login()
        response = self.client.get('/api/user/66/roles')
        assert response.status_code == 404

    def test_all_roles(self):
        self.login()
        response = self.client.get('/api/roles')

        result_roles = response.json
        assert len(result_roles['roles']) == len(STATIC_ROLES)

    def test_roles_add(self):
        data = {"roles": [
            {"name": ROLE.APPLICATION_DEVELOPER.value},
            {"name": ROLE.PATIENT.value},
            {"name": ROLE.ADMIN.value}
        ]}

        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()
        response = self.client.put(
            '/api/user/%s/roles' % TEST_USER_ID,
            content_type='application/json', data=json.dumps(data))

        assert response.status_code == 200
        doc = response.json
        assert len(doc['roles']) == len(data['roles'])
        user = User.query.get(TEST_USER_ID)
        assert len(user.roles) == len(data['roles'])
        title_case_name = [
            r['display_name'] for r in doc['roles']
            if r['name'] == 'application_developer'][0]
        assert 'Application Developer' == title_case_name

    def test_roles_post(self):
        data = {"roles": [
            {"name": ROLE.APPLICATION_DEVELOPER.value},
            {"name": ROLE.PATIENT.value}
        ]}

        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()
        response = self.client.post(
            '/api/user/%s/roles' % TEST_USER_ID,
            content_type='application/json', data=json.dumps(data))

        assert response.status_code == 200
        doc = response.json
        assert len(doc['roles']) == 3
        user = User.query.get(TEST_USER_ID)
        assert len(user.roles) == len(doc['roles'])

    def test_roles_duplicate_add(self):
        data = {"roles": [
            {"name": ROLE.APPLICATION_DEVELOPER.value},
        ]}

        self.promote_user(role_name=ROLE.ADMIN.value)
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER.value)
        self.login()
        response = self.client.put(
            '/api/user/%s/roles' % TEST_USER_ID,
            content_type='application/json', data=json.dumps(data))

        assert response.status_code == 200
        doc = response.json
        assert len(doc['roles']) == 1
        assert doc['roles'][0]['name'] == data['roles'][0]['name']
        user = User.query.get(TEST_USER_ID)
        assert len(user.roles) == 1

    def test_roles_duplicate_post(self):
        """POST shouldn't allow duplicates"""
        data = {"roles": [
            {"name": ROLE.APPLICATION_DEVELOPER.value},
        ]}

        self.promote_user(role_name=ROLE.ADMIN.value)
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER.value)
        self.login()
        response = self.client.post(
            '/api/user/%s/roles' % TEST_USER_ID,
            content_type='application/json',
            data=json.dumps(data))

        assert response.status_code == 409
        user = User.query.get(TEST_USER_ID)
        assert len(user.roles) == 2

    def test_roles_delete_via_put(self):
        "delete via PUT of less than all current roles"
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.promote_user(role_name=ROLE.ADMIN.value)
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER.value)
        data = {"roles": [
            {"name": ROLE.ADMIN.value},
            {"name": ROLE.APPLICATION_DEVELOPER.value},
        ]}

        self.login()
        response = self.client.put(
            '/api/user/%s/roles' % TEST_USER_ID,
            content_type='application/json', data=json.dumps(data))

        assert response.status_code == 200
        doc = response.json
        assert len(doc['roles']) == 2
        user = User.query.get(TEST_USER_ID)
        assert len(user.roles) == 2

    def test_roles_delete(self):
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.promote_user(role_name=ROLE.ADMIN.value)
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER.value)
        data = {"roles": [{"name": ROLE.PATIENT.value}]}

        self.login()
        response = self.client.delete(
            '/api/user/%s/roles' % TEST_USER_ID,
            content_type='application/json', data=json.dumps(data))

        assert response.status_code == 200
        doc = response.json
        assert len(doc['roles']) == 2
        user = User.query.get(TEST_USER_ID)
        assert len(user.roles) == 2

    def test_roles_nochange(self):
        data = {"roles": [
            {"name": ROLE.PATIENT.value},
            {"name": ROLE.ADMIN.value}
        ]}

        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()
        response = self.client.put(
            '/api/user/%s/roles' % TEST_USER_ID,
            content_type='application/json', data=json.dumps(data))

        assert response.status_code == 200
        doc = response.json
        assert len(doc['roles']) == len(data['roles'])
        user = User.query.get(TEST_USER_ID)
        assert len(user.roles) == len(data['roles'])

    def test_prevent_service_role(self):
        "Don't allow promotion of accounts to service"
        data = {"roles": [
            {"name": ROLE.SERVICE.value},
            {"name": ROLE.ADMIN.value}
        ]}

        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()
        response = self.client.put(
            '/api/user/%s/roles' % TEST_USER_ID,
            content_type='application/json', data=json.dumps(data))

        assert response.status_code == 400

    def test_user_check_roles(self):
        org = Organization(name='members only')
        user = self.test_user
        user.organizations.append(org)
        u2 = self.add_user(username='u2@foo.com')
        member_of = self.add_user(username='member_of@example.com')
        member_of.organizations.append(org)
        audit = Audit(
            comment='test data', user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        self.promote_user(user, ROLE.STAFF.value)
        self.promote_user(u2, ROLE.PATIENT.value)
        self.promote_user(member_of, ROLE.PATIENT.value)
        user, org, u2, member_of = map(
            db.session.merge, (user, org, u2, member_of))
        consent = UserConsent(
            user_id=member_of.id, organization_id=org.id,
            audit=audit, agreement_url='http://example.org',
            research_study_id=0, options=STAFF_EDITABLE_MASK)
        with SessionScope(db):
            db.session.add(consent)
            db.session.commit()
        user, org, u2, member_of = map(
            db.session.merge, (user, org, u2, member_of))

        kwargs = {'permission': 'view', 'other_id': user.id}
        assert user.check_role(**kwargs)

        kwargs = {'permission': 'edit', 'other_id': u2.id}
        with pytest.raises(Unauthorized):
            user.check_role(**kwargs)

        kwargs = {'permission': 'view', 'other_id': u2.id}
        with pytest.raises(Unauthorized):
            user.check_role(**kwargs)

        kwargs = {'permission': 'edit', 'other_id': member_of.id}
        assert user.check_role(**kwargs)

        kwargs = {'permission': 'view', 'other_id': member_of.id}
        assert user.check_role(**kwargs)

    def test_deep_tree_check_role(self):
        self.deepen_org_tree()

        org_102 = Organization.query.get(102)
        org_1002 = Organization.query.get(1002)
        org_10031 = Organization.query.get(10031)
        org_10032 = Organization.query.get(10032)
        audit = Audit(comment="testing", user_id=TEST_USER_ID,
                      subject_id=TEST_USER_ID, context='consent')

        staff_top = self.add_user('Staff 102')
        self.promote_user(staff_top, ROLE.STAFF.value)
        staff_top = db.session.merge(staff_top)
        staff_top.organizations.append(org_102)

        staff_leaf = self.add_user('Staff 10031')
        self.promote_user(staff_leaf, ROLE.STAFF.value)
        staff_leaf = db.session.merge(staff_leaf)
        staff_leaf.organizations.append(org_10031)

        staff_mid = self.add_user('Staff 1002')
        self.promote_user(staff_mid, ROLE.STAFF.value)
        staff_mid = db.session.merge(staff_mid)
        staff_mid.organizations.append(org_1002)

        patient_w = self.add_user('patient w')
        patient_w_id = patient_w.id
        self.promote_user(patient_w, ROLE.PATIENT.value)
        patient_w = db.session.merge(patient_w)
        patient_w.organizations.append(org_10032)
        uc_w = UserConsent(
            audit=audit, agreement_url='http://fake.org',
            user_id=patient_w_id, organization=org_10032,
            research_study_id=0, options=STAFF_EDITABLE_MASK)

        patient_x = self.add_user('patient x')
        patient_x_id = patient_x.id
        self.promote_user(patient_x, ROLE.PATIENT.value)
        patient_x = db.session.merge(patient_x)
        patient_x.organizations.append(org_10032)
        uc_x = UserConsent(
            audit=audit, agreement_url='http://fake.org',
            user_id=patient_x_id, organization=org_102,
            research_study_id=0, options=STAFF_EDITABLE_MASK)

        patient_y = self.add_user('patient y')
        patient_y_id = patient_y.id
        self.promote_user(patient_y, ROLE.PATIENT.value)
        patient_y = db.session.merge(patient_y)
        patient_y.organizations.append(org_102)
        uc_y = UserConsent(
            audit=audit, agreement_url='http://fake.org',
            user_id=patient_y_id, organization=org_10031,
            research_study_id=0, options=STAFF_EDITABLE_MASK)

        patient_z = self.add_user('patient z')
        patient_z_id = patient_z.id
        self.promote_user(patient_z, ROLE.PATIENT.value)
        patient_z = db.session.merge(patient_z)
        patient_z.organizations.append(org_10031)
        uc_z = UserConsent(
            audit=audit, agreement_url='http://fake.org',
            user_id=patient_z_id, organization=org_10031,
            research_study_id=0, options=STAFF_EDITABLE_MASK)

        with SessionScope(db):
            db.session.add(uc_w)
            db.session.add(uc_x)
            db.session.add(uc_y)
            db.session.add(uc_z)
            db.session.commit()
        patient_w, patient_x, patient_y, patient_z = map(db.session.merge, (
            patient_w, patient_x, patient_y, patient_z))

        ###
        # Setup complete - test access
        ###

        # top level staff can view/edit all
        staff_top = db.session.merge(staff_top)
        for perm in ('view', 'edit'):
            for patient in (
                patient_w_id, patient_x_id, patient_y_id, patient_z_id
            ):
                assert staff_top.check_role(perm, other_id=patient)

        # mid level staff can view/edit all
        staff_mid = db.session.merge(staff_mid)
        for perm in ('view', 'edit'):
            for patient in (
                patient_w_id, patient_x_id, patient_y_id, patient_z_id
            ):
                assert staff_mid.check_role(perm, other_id=patient)

        # low level staff can view/edit only those w/ same org
        staff_leaf = db.session.merge(staff_leaf)
        for perm in ('view', 'edit'):
            for patient in (patient_w_id, patient_x_id):
                with pytest.raises(Unauthorized):
                    staff_leaf.check_role(perm, patient)
        for perm in ('view', 'edit'):
            for patient in (patient_y_id, patient_z_id):
                assert staff_leaf.check_role(perm, other_id=patient)

        # Now remove the staff editable flag from the consents, which should
        # preserve view but remove edit permission
        for uc in (uc_w, uc_x, uc_y, uc_z):
            uc = db.session.merge(uc)
            uc.staff_editable = False

        with SessionScope(db):
            db.session.commit()
        patient_w, patient_x, patient_y, patient_z = map(db.session.merge, (
            patient_w, patient_x, patient_y, patient_z))

        # top level staff can view all, edit none
        staff_top = db.session.merge(staff_top)
        for patient in (
            patient_w_id, patient_x_id, patient_y_id, patient_z_id
        ):
            assert staff_top.check_role('view', other_id=patient)
            with pytest.raises(Unauthorized):
                staff_top.check_role('edit', other_id=patient)

        # mid level staff can view all, edit none
        staff_mid = db.session.merge(staff_mid)
        for patient in (
            patient_w_id, patient_x_id, patient_y_id, patient_z_id
        ):
            assert staff_mid.check_role('view', other_id=patient)
            with pytest.raises(Unauthorized):
                staff_mid.check_role('edit', other_id=patient)

        # low level staff can view only those w/ same org; edit none
        staff_leaf = db.session.merge(staff_leaf)
        for perm in ('view', 'edit'):
            for patient in (patient_w_id, patient_x_id):
                with pytest.raises(Unauthorized):
                    staff_leaf.check_role(perm, patient)
        for patient in (patient_y_id, patient_z_id):
            assert staff_leaf.check_role('view', other_id=patient)
            with pytest.raises(Unauthorized):
                staff_leaf.check_role('edit', patient)

    def test_deep_tree_staff_check_role(self):
        """Can staff-admin edit correct staff members"""
        self.deepen_org_tree()

        org_102 = Organization.query.get(102)
        org_1002 = Organization.query.get(1002)
        org_10031 = Organization.query.get(10031)
        org_10032 = Organization.query.get(10032)

        staff_admin_top = self.add_user('staff_admin 102')
        self.promote_user(staff_admin_top, ROLE.STAFF_ADMIN.value)
        staff_admin_top = db.session.merge(staff_admin_top)
        staff_admin_top.organizations.append(org_102)

        staff_admin_leaf = self.add_user('staff_admin 10031')
        self.promote_user(staff_admin_leaf, ROLE.STAFF_ADMIN.value)
        staff_admin_leaf = db.session.merge(staff_admin_leaf)
        staff_admin_leaf.organizations.append(org_10031)

        staff_admin_mid = self.add_user('staff_admin 1002')
        self.promote_user(staff_admin_mid, ROLE.STAFF_ADMIN.value)
        staff_admin_mid = db.session.merge(staff_admin_mid)
        staff_admin_mid.organizations.append(org_1002)

        staff_w = self.add_user('staff w')
        self.promote_user(staff_w, ROLE.STAFF.value)
        staff_w = db.session.merge(staff_w)
        staff_w.organizations.append(org_10032)

        staff_x = self.add_user('staff x')
        staff_x_id = staff_x.id
        self.promote_user(staff_x, ROLE.STAFF.value)
        staff_x = db.session.merge(staff_x)
        staff_x.organizations.append(org_10032)

        staff_y = self.add_user('staff y')
        staff_y_id = staff_y.id
        self.promote_user(staff_y, ROLE.STAFF.value)
        staff_y = db.session.merge(staff_y)
        staff_y.organizations.append(org_102)

        staff_z = self.add_user('staff z')
        staff_z_id = staff_z.id
        self.promote_user(staff_z, ROLE.STAFF.value)
        staff_z = db.session.merge(staff_z)
        staff_z.organizations.append(org_10031)

        ###
        # Setup complete - test access
        ###

        # top level staff_admin can view/edit all
        staff_admin_top = db.session.merge(staff_admin_top)
        for perm in ('view', 'edit'):
            for staff in (
                    staff_x_id, staff_y_id, staff_z_id):
                assert staff_admin_top.check_role(perm, other_id=staff)

        # mid level staff_admin can view/edit all but top
        staff_admin_mid = db.session.merge(staff_admin_mid)
        for perm in ('view', 'edit'):
            for staff in (
                    staff_x_id, staff_z_id):
                assert staff_admin_mid.check_role(perm, other_id=staff)
            with pytest.raises(Unauthorized):
                staff_admin_mid.check_role(perm, other_id=staff_y_id)

        # low level staff_admin can view/edit only those w/ same org
        staff_admin_leaf = db.session.merge(staff_admin_leaf)
        for perm in ('view', 'edit'):
            for staff in (staff_y_id, staff_x_id):
                with pytest.raises(Unauthorized):
                    staff_admin_leaf.check_role(perm, staff)
            assert staff_admin_leaf.check_role(perm, other_id=staff_z_id)

    def test_all_relationships(self):
        # obtain list of all relationships
        response = self.client.get('/api/relationships')
        assert response.status_code == 200
        assert len(response.json['relationships']) >= 2  # we'll add more

    def create_fake_relationships(self):
        other_user = self.add_user(username='other@foo.com')
        partner = Relationship.query.filter_by(name='partner').first()
        rel = UserRelationship(user_id=TEST_USER_ID,
                               relationship_id=partner.id,
                               other_user_id=other_user.id)
        sponsor = Relationship.query.filter_by(name='sponsor').first()
        rel2 = UserRelationship(
            user_id=other_user.id, relationship_id=sponsor.id,
            other_user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(rel)
            db.session.add(rel2)
            db.session.commit()

    def test_subject_relationships(self):
        # make sure we get relationships for both subject and predicate
        self.create_fake_relationships()
        self.login()
        response = self.client.get('/api/user/{}/relationships'.format(
            TEST_USER_ID))
        assert response.status_code == 200
        assert len(response.json['relationships']) >= 2  # we'll add more

    def test_set_relationships(self):
        other_user = self.add_user(username='other@foo.com')
        data = {'relationships': [{
            'user': TEST_USER_ID,
            'has the relationship': 'partner',
            'with': other_user.id}, ]
        }
        self.login()
        response = self.client.put('/api/user/{}/relationships'.format(
            TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200

        ur = UserRelationship.query.filter_by(
            other_user_id=other_user.id).first()
        assert ur.relationship.name == RELATIONSHIP.PARTNER.value

    def test_put_relationships(self):
        """PUT defines the whole list for a user - deletes unnamed existing"""
        # fake relationships creates 1 as subj and another as predicate
        self.create_fake_relationships()
        self.test_user = db.session.merge(self.test_user)

        # self.test_user.relationships only includes subject relations
        assert len(self.test_user.relationships) == 1

        self.login()
        response = self.client.get('/api/user/{}/relationships'.format(
            TEST_USER_ID))
        assert response.status_code == 200
        data = response.json

        # includes subj and predicate relations
        assert len(data['relationships']) == 2

        # Now, just PUT the subject one of the two
        data['relationships'] = [r for r in data['relationships'] if
                                 r['user'] == self.test_user.id]
        assert len(data['relationships']) == 1
        response = self.client.put('/api/user/{}/relationships'.format(
            TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200
        assert len(response.json['relationships']) == 1
        assert len(self.test_user.relationships) == 1

    def test_delete_relationships(self):
        "delete now done by PUTting less than all relationships"
        self.create_fake_relationships()
        other_user = User.query.filter_by(username='other@foo.com').first()
        data = {'relationships': [{
            'user': other_user.id,
            'has the relationship': 'sponsor',
            'with': TEST_USER_ID}]}
        self.login()
        response = self.client.put('/api/user/{}/relationships'.format(
            TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 200

        # shouldn't find the deleted (the one not PUT above)
        ur = UserRelationship.query.filter_by(
            other_user_id=other_user.id).first()
        assert not ur

        # but the one PUT should remain
        ur = UserRelationship.query.filter_by(
            other_user_id=TEST_USER_ID).first()
        assert ur.relationship.name == RELATIONSHIP.SPONSOR.value

    def test_fuzzy_match(self):
        self.test_user.birthdate = "01-31-1950"
        with SessionScope(db):
            db.session.commit()
        user = db.session.merge(self.test_user)
        score = user.fuzzy_match(first_name=user.first_name,
                                 last_name=user.last_name,
                                 birthdate=user.birthdate)
        assert score == 100  # should be perfect match

        score = user.fuzzy_match(
            first_name=user.first_name,
            last_name=user.last_name,
            birthdate=datetime.strptime("01-31-1951", '%m-%d-%Y'),
        )
        assert score == 0  # incorrect birthdate returns 0

        score = user.fuzzy_match(first_name=user.first_name,
                                 last_name='O' + user.last_name,
                                 birthdate=user.birthdate)
        assert score > 88  # should be close

        score = user.fuzzy_match(first_name=user.first_name,
                                 last_name='wrong',
                                 birthdate=user.birthdate)
        assert score < 51  # Name 1/2 correct

    def test_merge(self):
        with SessionScope(db):
            other = self.add_user('other@foo.com', first_name='newFirst',
                                  last_name='Better')
            other.birthdate = '02-05-1968'
            other.gender = 'male'
            other.timezone = 'US/Eastern'
            self.shallow_org_tree()
            orgs = Organization.query.limit(2)
            other = db.session.merge(other)
            ap = AuthProvider(provider_id=0, user=other)
            db.session.add(ap)
            other.organizations.append(orgs[0])
            other.organizations.append(orgs[1])
            deceased_audit = Audit(
                user_id=TEST_USER_ID, comment='n/a', subject_id=TEST_USER_ID)
            other.deceased = deceased_audit
            db.session.commit()
            user, other = map(db.session.merge, (self.test_user, other))
            user.timezone = 'US/Central'  # want to retain the original
            user.merge_with(other.id)
            db.session.commit()
            user, other = map(db.session.merge, (user, other))
            assert user.first_name == 'newFirst'
            assert user.last_name == 'Better'
            assert user.gender == 'male'
            assert ({o.name for o in user.organizations}
                    == {o.name for o in orgs})
            assert user.deceased
            assert user.timezone == 'US/Central'
            assert user.auth_providers.count() == 1
            assert other.auth_providers.count() == 0

    def test_promote(self):
        with SessionScope(db):
            self.test_user.password = None  # mock pre-registered user
            self.test_user.birthdate = '02-05-1968'
            self.promote_user(self.test_user, role_name=ROLE.WRITE_ONLY.value)
            other = self.add_user('other@foo.com', first_name='newFirst',
                                  last_name='Better')
            other.password = 'phoney'
            other.gender = 'male'
            self.shallow_org_tree()
            orgs = Organization.query.limit(2)
            self.test_user = db.session.merge(self.test_user)
            self.test_user.organizations.append(orgs[0])
            self.test_user.organizations.append(orgs[1])
            db.session.commit()
            user, other = map(db.session.merge, (self.test_user, other))
            old_regtime = user.registered
            assert not user.is_registered()
            user.promote_to_registered(other)
            db.session.commit()
            user, other = map(db.session.merge, (user, other))
            assert user.is_registered()
            assert user.registered != old_regtime
            assert other.deleted
            assert user.first_name == 'newFirst'
            assert user.last_name == 'Better'
            assert user.gender == 'male'
            assert user.password == 'phoney'
            assert ({o.name for o in user.organizations}
                    == {o.name for o in orgs})

    def test_promote_to_registered_fails_when_target_is_power_user(self):
        with SessionScope(db):
            self.test_user.password = None  # mock pre-registered user
            self.test_user.birthdate = '02-05-1968'
            self.promote_user(self.test_user, role_name=ROLE.WRITE_ONLY.value)
            other = self.add_user('other@foo.com', first_name='newFirst',
                                  last_name='Better')
            other.password = 'phoney'
            other.gender = 'male'
            self.promote_user(user=other, role_name=ROLE.ADMIN.value)
            self.shallow_org_tree()
            orgs = Organization.query.limit(2)
            self.test_user = db.session.merge(self.test_user)
            self.test_user.organizations.append(orgs[0])
            self.test_user.organizations.append(orgs[1])
            db.session.commit()
            user, other = map(db.session.merge, (self.test_user, other))
            with self.assertRaises(HTTPException) as http_error:
                user.promote_to_registered(other)
                assert http_error.exception.code == 400

    def test_password_reset(self):
        self.promote_user(role_name=ROLE.ADMIN.value)
        self.set_user_locale()
        self.login()

        response = self.client.post('/api/user/{}/password_reset'.format(
            TEST_USER_ID),
            content_type='application/json')

        assert response.status_code == 200

    def test_bogus_user_contensent(self):
        # example bogus data from msk testing
        data = {
            'agreement_url':
                'https://stg-lr7.us.truenth.org/c/portal/truenth/asset?'
                'editorUrl=true&version=1.6&groupId=20147&'
                'uuid=09bb5690-d49b-a10e-5339-e677353e694f',
            'user_id': '{}'.format(TEST_USER_ID),
            'include_in_reports': True,
            'send_reminders': False,
            'organization_id': '%22',
            'staff_editable': True,
            'org': '22110'}
        self.login()
        response = self.client.post(
            '/api/user/{}/consent'.format(TEST_USER_ID), data=json.dumps(data),
            content_type='application/json')
        assert response.status_code == 400

    def test_locale_inheritance(self):
        # prepopuate database with matching locale
        cd = Coding.from_fhir({
            'code': 'en_AU', 'display': 'Australian English',
            'system': "urn:ietf:bcp:47"})
        # create parent with locale
        parent_id = 101
        parent = Organization(id=parent_id, name='test parent')
        ol = OrganizationLocale(organization_id=parent_id, coding_id=cd.id)
        # create child org with no locales
        org = Organization(id=102, name='test', partOf_id=parent_id)
        org.use_specific_codings = False
        with SessionScope(db):
            db.session.add(parent)
            db.session.commit()
            db.session.add(ol)
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        assert org.partOf_id == parent_id
        # add child org to user
        user = User.query.get(TEST_USER_ID)
        user.organizations.append(org)
        # test locale inheritance
        assert user.locale_display_options['en_AU'] == 'Australian English'

    def test_user_messages(self):
        msg1 = EmailMessage(subject='Test #1',
                            recipients=TEST_USERNAME,
                            sender='__system__',
                            body='Test message.',
                            sent_at=datetime.utcnow())

        msg2 = EmailMessage(subject='Test #2',
                            recipients=TEST_USERNAME,
                            sender='__system__',
                            body='Test message.',
                            sent_at=datetime.utcnow())

        with SessionScope(db):
            db.session.add(msg1)
            db.session.add(msg2)
            db.session.commit()

        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()
        resp = self.client.get('/api/user/{}/messages'.format(TEST_USER_ID))

        assert resp.status_code == 200
        assert len(resp.json['messages']) == 2
        assert resp.json['messages'][0]['body'] == 'Test message.'

    def test_invite(self):
        su = self.add_service_user()
        self.login(su.id)

        resp = self.client.post('/api/user/{}/invite'.format(TEST_USER_ID))
        assert resp.status_code == 200

        # without a valid email address, should get a friendly message
        user = db.session.merge(self.test_user)
        user.email = 'xxxxxxx'

        with SessionScope(db):
            db.session.commit()

        resp = self.client.post('/api/user/{}/invite'.format(TEST_USER_ID))
        assert resp.status_code == 400
        assert 'requires a valid email' in resp.get_data(as_text=True)

    def test_email_not_ready(self):
        # with valid email and `NO_CHALLENGE_WO_DATA` set, should pass
        self.test_user.email = 'valid@email.org'
        self.app.config["NO_CHALLENGE_WO_DATA"] = True
        assert self.test_user.email_ready()[0]

        # alter config and expect failure w/o all DOB, first & last name
        self.app.config['NO_CHALLENGE_WO_DATA'] = False
        self.test_user.birthdate = None
        ready, reason = self.test_user.email_ready()
        assert not ready
        assert 'birthdate' in reason

        # set required fields and expect a pass
        self.test_user.birthdate = '1976-04-01'
        self.test_user.first_name = 'Ready'
        self.test_user.last_name = 'Set'
        assert self.test_user.email_ready()[0]

    def test_email_ready_api(self):
        # with valid invite email, `NO_CHALLENGE_WO_DATA` unset
        # and all challenge fields, should pass
        self.app.config["NO_CHALLENGE_WO_DATA"] = False
        self.test_user.email = '__invite__armistice@email.org'
        self.test_user.birthdate = '1912-12-03'
        with SessionScope(db):
            db.session.commit()
        self.login()
        response = self.client.get("/api/user/{}/email_ready".format(
            TEST_USER_ID))
        assert response.status_code == 200
        assert response.json['ready']

        # remove last_name from user, expect failure and details
        self.test_user = db.session.merge(self.test_user)
        self.test_user.last_name = None
        with SessionScope(db):
            db.session.commit()
        response = self.client.get("/api/user/{}/email_ready".format(
            TEST_USER_ID))
        assert response.status_code == 200
        assert not response.json['ready']
        assert 'last_name' in response.json['reason']
