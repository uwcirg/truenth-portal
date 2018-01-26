"""General Practitioner module"""
from ..database import db
from .telecom import ContactPoint, Telecom


class Practitioner(db.Model):
    __tablename__ = 'practitioners'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64), nullable=False)
    phone_id = db.Column(db.Integer, db.ForeignKey('contact_points.id',
                                                   ondelete='cascade'))

    _phone = db.relationship('ContactPoint', foreign_keys=phone_id,
                             cascade="save-update, delete")

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "practitioner {0.id}".format(self)

    @property
    def display_name(self):
        if self.first_name and self.last_name:
            name = ' '.join((self.first_name, self.last_name))
        name = name or 'Dr. {}'.format(self.last_name)
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

    def update_from_fhir(self, fhir, acting_user):
        """Update the practitioner data from the given FHIR

        If a field is defined, it is the final definition for the respective
        field, resulting in a deletion of existing values in said field
        that are not included.

        :param fhir: JSON defining portions of the user demographics to change

        """
        def v_or_n(val):
            return val.rstrip() if val else None

        if 'name' in fhir:
            self.first_name = v_or_n(
                fhir['name'].get('given')) or self.first_name
            self.last_name = v_or_n(
                fhir['name'].get('family')) or self.last_name
        if 'telecom' in fhir:
            telecom = Telecom.from_fhir(fhir['telecom'])
            telecom_cps = telecom.cp_dict()
            self.phone = telecom_cps.get(('phone', 'work')) or self.phone

    def as_fhir(self):
        d = {}
        d['resourceType'] = "Practitioner"
        d['name'] = {}
        d['name']['given'] = self.first_name
        d['name']['family'] = self.last_name
        telecom = Telecom(contact_points=[self._phone])
        d['telecom'] = telecom.as_fhir()
        return d
