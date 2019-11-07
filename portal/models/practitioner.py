"""Practitioner module"""
from html import escape

from sqlalchemy import UniqueConstraint

from ..database import db
from .fhir import v_or_first, v_or_n
from .identifier import Identifier
from .telecom import ContactPoint, Telecom


class Practitioner(db.Model):
    """Practitioner model for storing physician information"""
    __tablename__ = 'practitioners'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120))
    phone_id = db.Column(db.Integer, db.ForeignKey('contact_points.id',
                                                   ondelete='cascade'))

    _phone = db.relationship('ContactPoint', foreign_keys=phone_id,
                             cascade="save-update, delete")
    identifiers = db.relationship('Identifier', lazy='dynamic',
                                  secondary="practitioner_identifiers")

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "Practitioner {0.id} {0.first_name} {0.last_name}".format(self)

    @property
    def display_name(self):
        if self.first_name and self.last_name:
            name = ' '.join((self.first_name, self.last_name))
        elif self.last_name:
            name = self.last_name
        else:
            raise ValueError("No name fields for practitioner: {0.id}".format(
                self))
        return escape(name)

    @property
    def phone(self):
        if self._phone:
            return self._phone.value

    @phone.setter
    def phone(self, val):
        if self._phone:
            if val:
                self._phone.value = val
            else:
                self._phone = None
        elif val:
            self._phone = ContactPoint(
                system='phone', use='work', value=val)

    @classmethod
    def from_fhir(cls, data):
        practitioner = cls()
        return practitioner.update_from_fhir(data)

    def update_from_fhir(self, fhir):
        """Update the practitioner data from the given FHIR

        If a field is defined, it is the final definition for the respective
        field, resulting in a deletion of existing values in said field
        that are not included.

        :param fhir: JSON defining portions of the user demographics to change

        """
        if 'name' in fhir:
            name = v_or_first(fhir['name'], 'name')
            self.first_name = v_or_n(
                v_or_first(name.get('given'), 'given name')
            ) or self.first_name
            self.last_name = v_or_n(
                v_or_first(name.get('family'), 'family name')
            ) or self.last_name
        if 'telecom' in fhir:
            telecom = Telecom.from_fhir(fhir['telecom'])
            telecom_cps = telecom.cp_dict()
            self.phone = telecom_cps.get(('phone', 'work')) or self.phone
            if telecom.email:
                if ((telecom.email != self.email) and
                        (Practitioner.query.filter_by(
                            email=telecom.email).count() > 0)):
                    abort(400, "email address already in use")
                self.email = telecom.email
        if 'identifier' in fhir:
            # track current identifiers - must remove any not requested
            remove_if_not_requested = [i for i in self.identifiers]
            for ident in fhir['identifier']:
                identifier = Identifier.from_fhir(ident).add_if_not_found()
                if identifier not in self.identifiers.all():
                    self.identifiers.append(identifier)
                else:
                    remove_if_not_requested.remove(identifier)
            for obsolete in remove_if_not_requested:
                self.identifiers.remove(obsolete)
        return self

    def as_fhir(self):
        d = {}
        d['resourceType'] = "Practitioner"
        name = {}
        name['given'] = self.first_name
        name['family'] = self.last_name
        d['name'] = [name]
        telecom = Telecom(email=self.email, contact_points=[self._phone])
        d['telecom'] = telecom.as_fhir()
        d['identifier'] = []
        for ident in self.identifiers:
            d['identifier'].append(ident.as_fhir())
        return d


class PractitionerIdentifier(db.Model):
    """link table for practitioner : n identifiers"""
    __tablename__ = 'practitioner_identifiers'
    id = db.Column(db.Integer, primary_key=True)
    practitioner_id = db.Column(db.ForeignKey(
        'practitioners.id', ondelete='cascade'), nullable=False)
    identifier_id = db.Column(db.ForeignKey(
        'identifiers.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint('practitioner_id', 'identifier_id',
                                       name='_practitioner_identifier'),)
