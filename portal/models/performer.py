"""Performer module - encapsulate the FHIR Performer resource"""
import json

from sqlalchemy import UniqueConstraint

from ..database import db
from .codeable_concept import CodeableConcept


class Performer(db.Model):
    """ORM for FHIR Performer - performers table"""
    __tablename__ = 'performers'
    id = db.Column(db.Integer, primary_key=True)
    reference_txt = db.Column(db.Text, nullable=False)
    """Text for performer (aka *actor*), i.e. {"reference": "patient/12"}"""

    codeable_concept_id = db.Column(db.ForeignKey('codeable_concepts.id'))
    """The codeable concept for performers including a role"""

    # nullable due to FHIR inconsistencies in performer attributes
    codeable_concept = db.relationship('CodeableConcept', cascade="save-update")
    __table_args__ = (UniqueConstraint(
        'reference_txt', 'codeable_concept_id',
        name='_reftxt_codeable_concept'),)

    def __str__(self):
        """Print friendly format for logging, etc."""
        if self.codeable_concept:
            return "Performer {0.reference_txt} {0.codeable_concept}".format(
                self)
        return "Performer {0.reference_txt}".format(self)

    def as_fhir(self):
        """Return self in JSON FHIR formatted string

        FHIR is not currently consistant in performer inclusion.  For example,
        Observation.performer is simply a list of Reference resources,
        whereas Procedure.performer is a list including the resource labeled
        as an *actor* and a codable concept labeled as the *role* defining
        the actor's role.

        :returns: the best JSON FHIR formatted string for the instance

        """
        if self.codeable_concept:
            return {"actor": self.reference_txt,
                    "role": self.codeable_concept.as_fhir()}
        return self.reference_txt

    @classmethod
    def from_fhir(cls, fhir):
        """Return performer instance from JSON FHIR formatted string

        See note in `as_fhir`, the format of a performer depends on
        context.  Populate `self.codeable_concept` only if it's included
        as a *role*.

        :returns: new performer instance from values in given *fhir*

        """
        instance = cls()
        if 'actor' in fhir:
            instance.reference_txt = json.dumps(fhir['actor'])
            if 'role' in fhir:
                cc = CodeableConcept.from_fhir(fhir['role'])
                instance.codeable_concept = cc.add_if_not_found()
        else:
            instance.reference_txt = json.dumps(fhir)
        return instance

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for matching, existing Performer.
        Populates self.id if found, adds to database first if not.

        """
        if self.id:
            return self

        # having a codable_concept is significant - match accordingly
        match_dict = {'reference_txt': self.reference_txt,
                      'codeable_concept_id': None}
        if self.codeable_concept:
            match_dict['codeable_concept_id'] = self.codeable_concept_id

        match = self.query.filter_by(**match_dict).first()
        if not match:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        elif self is not match:
            self = db.session.merge(match)
        return self


class ObservationPerformer(db.Model):
    """Link table for observation to list of performers"""
    __tablename__ = 'observation_performers'
    id = db.Column(db.Integer(), primary_key=True)
    observation_id = db.Column(
        db.Integer(), db.ForeignKey('observations.id', ondelete='CASCADE'),
        nullable=False)
    performer_id = db.Column(
        db.Integer(), db.ForeignKey('performers.id', ondelete='CASCADE'),
        nullable=False)

    __table_args__ = (UniqueConstraint(
        'observation_id', 'performer_id', name='_obs_performer'),)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "ObservationPerformer {0.observation_id}:{0.performer_id}". \
            format(self)
