"""Unit test module for telecom model"""
from tests import TestCase

from portal.models.telecom import Telecom

class TestTelecom(TestCase):
    """Telecom model tests"""

    def test_from_fhir(self):
        data = [
            {
                "system": "phone",
                "value": "(+1) 734-677-7777"
            },
            {
                "system": "fox",
                "value": "(+1) 734-677-6622"
            },
            {
                "system": "email",
                "value": "hq@HL7.org"
            },
            {
                "system": "email",
                "value": "second_email@HL7.org"
            }
        ]
        tc = Telecom.from_fhir(data)
        self.assertEquals(tc.phone, "(+1) 734-677-7777")
        self.assertEquals(tc.email, "hq@HL7.org")
