from datetime import datetime

from ..database import db
from ..date_tools import FHIR_datetime, as_fhir
from .coding import Coding
from .codeable_concept import CodeableConcept
from .performer import Performer
from .value_quantity import ValueQuantity
from .reference import Reference


class Observation(db.Model):
    __tablename__ = 'observations'
    id = db.Column(db.Integer, primary_key=True)
    issued = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(80))
    codeable_concept_id = db.Column(
        db.ForeignKey('codeable_concepts.id'), nullable=False)
    value_quantity_id = db.Column(db.ForeignKey('value_quantities.id'))
    value_coding_id = db.Column(db.ForeignKey('codings.id'))
    codeable_concept = db.relationship(
        'CodeableConcept', cascade="save-update")
    value_quantity = db.relationship('ValueQuantity')
    value_coding = db.relationship('Coding')
    performers = db.relationship(
        'Performer', lazy='dynamic', cascade="save-update",
        secondary="observation_performers", backref=db.backref('observations'))
    derived_from = db.Column(db.Text, index=True)

    def __str__(self):
        """Print friendly format for logging, etc."""
        at = ' at {0.issued}'.format(self) if self.issued else ''
        status = ' with status {0.status}'.format(self) if self.status else ''
        return (
            "Observation {0.codeable_concept} {0.value_quantity}{at}"
            "{status}".format(self, at=at, status=status))

    def as_fhir(self):
        """Return self in JSON FHIR formatted string"""
        from .questionnaire_response import QuestionnaireResponse

        fhir = {"resourceType": "Observation"}
        if self.issued:
            fhir['issued'] = as_fhir(self.issued)
        if self.status:
            fhir['status'] = self.status
        fhir['id'] = self.id
        fhir['code'] = self.codeable_concept.as_fhir()
        if self.value_quantity_id:
            fhir.update(self.value_quantity.as_fhir())
        if self.value_coding_id:
            fhir.update(self.value_coding.as_fhir())
        if self.performers:
            fhir['performer'] = [p.as_fhir() for p in self.performers]
        if self.derived_from:
            # Only QNRs supported - if defined, it is a QNR.id.
            # In FHIR format, present as single item list reference
            qnr = QuestionnaireResponse.query.get(self.derived_from)
            ref = Reference.questionnaire_response(qnr.document_identifier)
            fhir['derivedFrom'] = [ref.as_fhir()]
        return fhir

    def update_from_fhir(self, data):
        if 'issued' in data:
            issued = FHIR_datetime.parse(data['issued']) if data[
                'issued'] else None
            setattr(self, 'issued', issued)
        if 'code' in data:
            self.codeable_concept = CodeableConcept.from_fhir(
                data['code'])
        if 'status' in data:
            setattr(self, 'status', data['status'])
        if 'performer' in data:
            for p in data['performer']:
                performer = Performer.from_fhir(p)
                self.performers.append(performer)
        if 'valueQuantity' in data:
            v = data['valueQuantity']
            current_v = self.value_quantity
            vq = ValueQuantity(
                value=v.get('value') if 'value' in v else current_v.value,
                units=v.get('units') or current_v.units,
                system=v.get('system') or current_v.system,
                code=v.get('code') or current_v.code).add_if_not_found(True)
            setattr(self, 'value_quantity_id', vq.id)
            setattr(self, 'value_quantity', vq)
        if 'valueCoding' in data:
            self.value_coding = Coding.from_fhir(
                data['valueCoding']).add_if_not_found(True)
            self.value_coding_id = self.value_coding.id
        if 'derivedFrom' in data:
            # The only reference supported at this time is a single
            # QuestionnaireResponse.  If given, must refer to
            # a value QNR in the system - store PK if found.
            if len(data['derivedFrom']) != 1:
                raise ValueError(
                    "only single QuestionnareResponse reference supported in "
                    "Observation.derivedFrom")
            qnr = Reference.parse(data['derivedFrom'][0])
            self.derived_from = qnr.id
        return self.as_fhir()

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for matching, existing Observation.
        Populates self.id if found, adds to database first if not.

        """
        if self.id:
            return self
        match_dict = {'issued': self.issued,
                      'status': self.status}
        if self.codeable_concept_id:
            match_dict['codeable_concept_id'] = self.codeable_concept_id
        if self.value_quantity_id:
            match_dict['value_quantity_id'] = self.value_quantity_id

        match = self.query.filter_by(**match_dict).first()
        if not match:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        elif self is not match:
            self = db.session.merge(match)
        return self


class UserObservation(db.Model):
    __tablename__ = 'user_observations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey(
        'users.id', ondelete='CASCADE'), nullable=False)
    observation_id = db.Column(
        db.ForeignKey('observations.id'), nullable=False)
    encounter_id = db.Column(db.ForeignKey(
        'encounters.id', name='user_observation_encounter_id_fk'),
        nullable=False)
    audit_id = db.Column(db.ForeignKey('audit.id'), nullable=False)
    audit = db.relationship('Audit', cascade="save-update, delete")
    encounter = db.relationship('Encounter', cascade='delete')
    # There was a time when UserObservations were constrained to
    # one per (user_id, observation_id).  As history is important
    # and the same observation may be made twice, this constraint
    # was removed.
