"""Modle classes for organizations and related entities.

Designed around FHIR guidelines for representation of organizations, locations
and healthcare services which are used to describe hospitals and clinics.
"""
import re
from sqlalchemy import UniqueConstraint

from .address import Address
from ..extensions import db
from .fhir import CodeableConcept
from .telecom import Telecom

class MissingReference(Exception):
    """Raised when organization references cannot be found"""
    pass


def parse_organization_id(reference_dict):
    """Organizations can refer to a parent organization as partOf

    Parse the id from the given reference_dict.  Expected format:
      "partOf": {
        "reference": "Organization/001"
      },

    @raise ValueError: if the format doesn't match
    @return the parsed id

    """
    pattern = re.compile('[Oo]rganization/(\d)+')

    reference_text = reference_dict['reference']
    match = pattern.search(reference_text)
    try:
        organization_id = int(match.groups()[0])
    except:
        raise ValueError('partOf reference not found: {}'.\
                         format(str(reference_text)))
    return organization_id


class Organization(db.Model):
    """Model representing a FHIR organization

    Organizations represent a collection of people that have come together
    to achieve an objective.  As an example, all the healthcare
    services provided by the same university hospital will belong to
    the organization representing said university hospital.

    Organizations can reference other organizations via the 'partOf_id',
    where children name their parent organization id.

    """
    __tablename__ = 'organizations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(40))
    type_id = db.Column(db.ForeignKey('codeable_concepts.id',
                                      ondelete='cascade'))
    partOf_id = db.Column(db.ForeignKey('organizations.id'))

    addresses = db.relationship('Address', lazy='dynamic',
            secondary="organization_addresses")
    type = db.relationship('CodeableConcept', cascade="save-update")

    def __str__(self):
        part_of = 'partOf {} '.format(self.partOf_id) if self.partOf_id else ''
        addresses = '; '.join([str(a) for a in self.addresses])

        return 'Organization {0.name} {0.type} {0.phone} {0.email} '.format(
                self) + part_of + addresses

    @classmethod
    def from_fhir(cls, data):
        org = cls()
        return org.update_from_fhir(data)

    @classmethod
    def from_fhir_reference(cls, data):
        """expects FHIR reference data - returns matching instance"""
        org_id = parse_organization_id(data)
        return cls.query.get(org_id)

    def update_from_fhir(self, data):
        if 'name' in data:
            self.name = data['name']
        if 'telecom' in data:
            telecom = Telecom.from_fhir(data['telecom'])
            self.phone = telecom.phone
            self.email = telecom.email
        if 'address' in data:
            for addr in data['address']:
                self.addresses.append(Address.from_fhir(addr))
        if 'type' in data:
            self.type = CodeableConcept.from_fhir(data['type'])
        if 'partOf' in data:
            self.partOf_id = parse_organization_id(data['partOf'])
            # Require the parent resource exists when named
            with db.session.no_autoflush:
                if not Organization.query.get(self.partOf_id):
                    raise MissingReference(
                        'Referenced Organization {} not found'.format(
                        self.partOf_id))
        return self

    def as_fhir(self):
        d = {}
        d['resourceType'] = 'Organization'
        d['id'] = self.id
        d['name'] = self.name
        telecom = Telecom(email=self.email, phone=self.phone)
        d['telecom'] = telecom.as_fhir()
        if self.addresses:
            d['address'] = []
        for addr in self.addresses:
            d['address'].append(addr.as_fhir())
        if self.type:
            d['type'] = self.type.as_fhir()
        if self.partOf_id:
            d['partOf'] = {'reference':
                           'organization/{}'.format(self.partOf_id)}
        return d


class UserOrganization(db.Model):
    """link table for users (n) : organizations (n)"""
    __tablename__ = 'user_organizations'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='cascade'), nullable=False)
    user_id = db.Column(db.ForeignKey(
        'users.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint('user_id', 'organization_id',
        name='_user_organization'),)


class OrganizationAddress(db.Model):
    """link table for organization : n addresses"""
    __tablename__ = 'organization_addresses'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='cascade'), nullable=False)
    address_id = db.Column(db.ForeignKey(
        'addresses.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint('organization_id', 'address_id',
        name='_observation_address'),)
