"""Questionnaire module"""
from sqlalchemy.dialects.postgresql import JSONB

from ..database import db


class Questionnaire(db.Model):
    __tablename__ = 'questionnaires'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    document = db.Column(JSONB)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "Questionnaire {0.id} {0.name}".format(self)

    @classmethod
    def from_fhir(cls, data):
        instance = cls()
        assert data['resourceType'] == 'Questionnaire'
        instance.name = data['name']
        return instance

    def as_fhir(self):
        d = {}
        d['resourceType'] = 'Questionnaire'
        d['name'] = self.name
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, matching on **name** alone.
        Note the database unique constraint to match.

        @return: the new or matched Questionnaire

        """
        assert self.name
        existing = Questionnaire.query.filter_by(name=self.name).first()
        if not existing:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        else:
            self.id = existing.id
        self = db.session.merge(self)
        return self
