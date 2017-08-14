"""Questionnaire module"""
from flask import url_for
from sqlalchemy.dialects.postgresql import JSONB

from ..database import db
from ..date_tools import FHIR_datetime


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

    @classmethod
    def generate_bundle(cls, limit_to_ids=None):
        """Generate a FHIR bundle of existing questionnaires ordered by ID

        If limit_to_ids is defined, only return the matching set, otherwise
        all questionnaires found.

        """
        query = Questionnaire.query.order_by(Questionnaire.id)
        if limit_to_ids:
            query = query.filter(Questionnaire.id.in_(limit_to_ids))

        objs = [q.as_fhir() for q in query]

        bundle = {
            'resourceType':'Bundle',
            'updated':FHIR_datetime.now(),
            'total':len(objs),
            'type': 'searchset',
            'link': {
                'rel':'self',
                'href':url_for('assessment_engine_api.questionnaire_list',
                               _external=True),
            },
            'entry':objs,
        }
        return bundle
