"""Unit test module for address model"""

from portal.models.address import Address


def test_from_fhir():
    data = {
        "line": ["3300 Washtenaw Avenue", "Suite 227"],
        "city": "Ann Arbor",
        "state": "MI",
        "postalCode": "48104",
        "country": "USA"
    }
    addr = Address.from_fhir(data)
    assert addr.line1 == data['line'][0]
    assert addr.city == data['city']
    assert addr.state == data['state']
    assert addr.postalCode == data['postalCode']
    assert 'Suite 227' in str(addr)


def test_as_fhir():
    addr = Address(city='Seattle', state='WA', postalCode='98101')
    data = addr.as_fhir()
    assert addr.city == data['city']
    assert addr.state == data['state']
    assert addr.postalCode == data['postalCode']
