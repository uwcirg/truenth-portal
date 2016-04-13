"""Unit test module for user model and views"""
from flask.ext.webtest import SessionScope
import json
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.fhir import Coding, UserEthnicity
from portal.models.relationship import Relationship, RELATIONSHIP
from portal.models.role import STATIC_ROLES, ROLE
from portal.models.user import User, UserEthnicityExtension, user_extension_map
from portal.models.user import UserRelationship

class TestUser(TestCase):
    """User model and view tests"""

    def test_unique_username(self):
        dup = User(username='with number 1')
        try_me = User(username='Anonymous', first_name='with',
                      last_name='number')
        with SessionScope(db):
            db.session.add(dup)
            db.session.add(try_me)
            db.session.commit()
        dup = db.session.merge(dup)
        try_me = db.session.merge(try_me)

        try_me.update_username()
        self.assertNotEquals(try_me.username, 'Anonymous')
        self.assertNotEquals(dup.username, try_me.username)

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
        self.assertEquals(2, self.test_user.ethnicities.count())

        extension = {"url":
            "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity"}
        kls = user_extension_map(user=self.test_user, extension=extension)
        self.assertTrue(isinstance(kls, UserEthnicityExtension))

        # generate FHIR from user's ethnicities
        fhir_data = kls.as_fhir()

        self.assertEquals(2, len(fhir_data['valueCodeableConcept']['coding']))
        codes = [c['code'] for c in fhir_data['valueCodeableConcept']['coding']]
        self.assertIn('2135-2', codes)
        self.assertIn('2142-8', codes)

        # now create a new extension (FHIR like) and apply to the user
        extension = {"url":
            "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity",
            "valueCodeableConcept": {
                "coding": [
                    {"system":
                     "http://hl7.org/fhir/v3/Ethnicity",
                     "code": "2162-6"
                    },
                    {"system":
                     "http://hl7.org/fhir/v3/Ethnicity",
                     "code": "2142-8"
                    },
                ]
            }}

        ue = UserEthnicityExtension(self.test_user, extension)
        ue.apply_fhir()
        self.assertEquals(2, self.test_user.ethnicities.count())
        found = [c.code for c in self.test_user.ethnicities]
        self.assertIn('2162-6', found)
        self.assertIn('2142-8', found)

    def test_ur_format(self):
        ur = UserRelationship(user_id=TEST_USER_ID, other_user_id=TEST_USER_ID,
                              relationship_id=1)
        db.session.add(ur)
        db.session.commit()
        ur_str = "test format {}".format(ur)
        self.assertIn('Relationship', ur_str)

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

