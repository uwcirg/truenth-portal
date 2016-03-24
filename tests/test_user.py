"""Unit test module for user model"""
from flask.ext.webtest import SessionScope
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.fhir import CodeableConcept, UserEthnicity
from portal.models.user import User, UserEthnicityExtension, user_extension_map


class TestUser(TestCase):
    """User model tests"""

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
        concepts = CodeableConcept.query.filter(CodeableConcept.code.in_(
            ('2142-8', '2135-2'))).all()
        with SessionScope(db):
            db.session.add(UserEthnicity(user_id=TEST_USER_ID,
                                         codeable_concept_id=concepts[0].id))
            db.session.add(UserEthnicity(user_id=TEST_USER_ID,
                                         codeable_concept_id=concepts[1].id))
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
