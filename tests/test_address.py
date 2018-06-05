"""Unit test module for address model"""
from tests import TestCase
from portal.models.address import Address


class TestAddress(TestCase):
    """Address model tests"""

    def test_from_fhir(self):
        data =  {
            "line": [ "3300 Washtenaw Avenue", "Suite 227"],
            "city": "Ann Arbor",
            "state": "MI",
            "postalCode": "48104",
            "country": "USA"
        }
        addr = Address.from_fhir(data)
        self.assertEqual(addr.line1, data['line'][0])
        self.assertEqual(addr.city, data['city'])
        self.assertEqual(addr.state, data['state'])
        self.assertEqual(addr.postalCode, data['postalCode'])
        self.assertIn('Suite 227', str(addr))

    def test_as_fhir(self):
        addr = Address(city='Seattle', state='WA', postalCode='98101')
        data = addr.as_fhir()
        self.assertEqual(addr.city, data['city'])
        self.assertEqual(addr.state, data['state'])
        self.assertEqual(addr.postalCode, data['postalCode'])
