"""Model classes for organizations and related entities.

Designed around FHIR guidelines for representation of organizations, locations
and healthcare services which are used to describe hospitals and clinics.
"""
from sqlalchemy import UniqueConstraint
from flask import url_for

import address
from ..extensions import db
from .fhir import CodeableConcept, FHIR_datetime
from .identifier import Identifier
import reference
from .telecom import Telecom


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
    email = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    type_id = db.Column(db.ForeignKey('codeable_concepts.id',
                                      ondelete='cascade'))
    partOf_id = db.Column(db.ForeignKey('organizations.id'))

    addresses = db.relationship('Address', lazy='dynamic',
            secondary="organization_addresses")
    identifiers = db.relationship('Identifier', lazy='dynamic',
            secondary="organization_identifiers")
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

    def update_from_fhir(self, data):
        if 'id' in data:
            self.id = data['id']
        if 'name' in data:
            self.name = data['name']
        if 'telecom' in data:
            telecom = Telecom.from_fhir(data['telecom'])
            self.phone = telecom.phone
            self.email = telecom.email
        if 'address' in data:
            for addr in data['address']:
                self.addresses.append(address.Address.from_fhir(addr))
        if 'type' in data:
            self.type = CodeableConcept.from_fhir(data['type'])
        if 'partOf' in data:
            self.partOf_id = reference.Reference.parse(data['partOf']).id
        if 'identifier' in data:
            for id in data['identifier']:
                identifier = Identifier.from_fhir(id).add_if_not_found()
                if identifier not in self.identifiers:
                    self.identifiers.append(identifier)
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
            d['partOf'] = reference.Reference.organization(
                self.partOf_id).as_fhir()
        if self.identifiers:
            d['identifier'] = []
        for id in self.identifiers:
            d['identifier'].append(id.as_fhir())
        return d

    @classmethod
    def generate_bundle(cls):
        """Generate a FHIR bundle of existing orgs ordered by ID"""

        query = Organization.query.order_by(Organization.id)
        orgs = [o.as_fhir() for o in query]

        bundle = {
            'resourceType':'Bundle',
            'updated':FHIR_datetime.now(),
            'total':len(orgs),
            'type': 'searchset',
            'link': {
                'rel':'self',
                'href':url_for(
                    'org_api.organization_list', _external=True),
            },
            'entry':orgs,
        }
        return bundle


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

    organization = db.relationship('Organization')

class OrganizationAddress(db.Model):
    """link table for organization : n addresses"""
    __tablename__ = 'organization_addresses'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='cascade'), nullable=False)
    address_id = db.Column(db.ForeignKey(
        'addresses.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint('organization_id', 'address_id',
        name='_organization_address'),)


class OrganizationIdentifier(db.Model):
    """link table for organization : n identifiers"""
    __tablename__ = 'organization_identifiers'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='cascade'), nullable=False)
    identifier_id = db.Column(db.ForeignKey(
        'identifiers.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint('organization_id', 'identifier_id',
        name='_organization_identifier'),)


def add_static_organization():
    """Insert special `none of the above` org at index 0"""
    existing = Organization.query.get(0)
    if not existing:
        db.session.add(Organization(id=0, name='none of the above'))
