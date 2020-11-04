from flask import current_app
from sqlalchemy import UniqueConstraint

from ..database import db


class Coding(db.Model):
    __tablename__ = 'codings'
    id = db.Column(db.Integer, primary_key=True)
    system = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(80), nullable=False)
    display = db.Column(db.Text, nullable=False)
    extension_id = db.Column(db.ForeignKey('codings.id'))
    extension = db.relationship('Coding', remote_side=[id])
    __table_args__ = (
        UniqueConstraint('system', 'code', name='_system_code'),)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "Coding {0.code}, {0.display}, {0.system}".format(self)

    def update_from_fhir(self, data):
        for i in ("system", "code", "display"):
            if i in data:
                self.__setattr__(i, str(data[i]))
        if 'extension' in data and len(data['extension']):
            # Only allow a single extension at this time
            if len(data['extension']) > 1:
                raise ValueError(
                    "codings model holds a single, optional extension")
            self.extension = Coding.from_fhir(
                data['extension'][0]['valueCoding']).add_if_not_found(True)
            self.extension_id = self.extension.id
        return self.add_if_not_found(True)

    @classmethod
    def from_fhir(cls, data):
        """Factory method to lookup or create instance from fhir"""
        cc = cls()
        return cc.update_from_fhir(data)

    def as_fhir(self):
        """Return self in JSON FHIR formatted string"""
        d = {}
        d['resourceType'] = 'Coding'

        for i in ("system", "code", "display"):
            if getattr(self, i) is not None:
                d[i] = getattr(self, i)
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, existing CodeableConcept (matches on
        system and code alone).  Populates self.id if found, adds
        to database first if not.

        """
        if self.id:
            return self

        if not (self.system and self.code):
            current_app.logger.error(
                "Ill defined coding {} - requires system and code"
                "".format(self))

        match = self.query.filter_by(
            system=self.system, code=self.code).first()
        if not match:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        elif self is not match:
            self = db.session.merge(match)
        return self

    @staticmethod
    def display_lookup(code, system):
        """Return display value for (code, system), if found"""
        item = Coding.query.filter(
            Coding.code == code,
            Coding.system == system).first()
        if not item:
            raise ValueError(
                "No coding found for ({system}, {code})".format(
                    system=system, code=code))
        return item.display
