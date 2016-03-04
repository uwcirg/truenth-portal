"""Unit test module for fhir model"""
from flask.ext.webtest import SessionScope
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.fhir import CodeableConcept


class TestFHIR(TestCase):
    """FHIR model tests"""

    def test_codeable_concept_parse(self):
        system = "urn:ietf:bcp:47"
        code = "nl"
        display = "Dutch"
        data = {"language":
                {"coding": [{"system": system,
                             "code": code,
                             "display": display}, ]
                }
               }
        cc = CodeableConcept.from_fhir(data['language'])
        self.assertEquals(cc.system, system)
        self.assertEquals(cc.code, code)
        self.assertEquals(cc.display, display)
