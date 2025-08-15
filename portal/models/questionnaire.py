"""Questionnaire module"""
from flask import url_for
from sqlalchemy import Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from ..database import db
from ..date_tools import FHIR_datetime
from ..system_uri import TRUENTH_QUESTIONNAIRE_CODE_SYSTEM
from .fhir import bundle_results
from .identifier import Identifier

status_types = ('draft', 'published', 'retired')
status_types_enum = Enum(
    *status_types, name='questionnaire_status_enum', create_type=False)


class Questionnaire(db.Model):
    """
    Questionnaire FHIR model
    Implemented against FHIR STU3
    """
    __tablename__ = 'questionnaires'
    id = db.Column(db.Integer, primary_key=True)
    identifiers = db.relationship(
        'Identifier', lazy='dynamic', secondary="questionnaire_identifiers")
    status = db.Column(
        'status', status_types_enum, server_default='draft', nullable=False)
    item = db.Column(JSONB)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "Questionnaire {0.id} {0.name}".format(self)

    @property
    def name(self):
        # Specific identifier is used as shorthand for name
        for i in self.identifiers:
            if i.system == TRUENTH_QUESTIONNAIRE_CODE_SYSTEM:
                return i.value
        return None

    @classmethod
    def find_by_name(cls, name):
        """Shortcut to fetch by named identifier with common system"""
        identifier = Identifier(
            _value=name,
            system=TRUENTH_QUESTIONNAIRE_CODE_SYSTEM,
        ).add_if_not_found()
        return cls.find_by_identifier(identifier)

    @classmethod
    def find_by_identifier(cls, identifier):
        """Query method to lookup by identifier"""
        q_ids = QuestionnaireIdentifier.query.filter(
            QuestionnaireIdentifier.identifier_id == identifier.id
        )
        if q_ids.count() > 1:
            raise ValueError(
                "Multiple Questionnaires mapped to {}".format(
                    identifier
                ))
        elif q_ids.count():
            first = q_ids.first()
            return cls.query.get(first.questionnaire_id)

    @classmethod
    def from_fhir(cls, data):
        instance = cls()
        return instance.update_from_fhir(data)

    def update_from_fhir(self, data):
        if 'identifier' in data:
            # track current identifiers - must remove any not requested
            remove_if_not_requested = [i for i in self.identifiers]
            for i in data['identifier']:
                identifier = Identifier.from_fhir(i).add_if_not_found()
                if identifier not in self.identifiers.all():
                    self.identifiers.append(identifier)
                else:
                    remove_if_not_requested.remove(identifier)
            for obsolete in remove_if_not_requested:
                self.identifiers.remove(obsolete)
        if 'status' in data:
            self.status = data.get('status')
        if 'item' in data:
            self.item = data.get('item')
        self = self.add_if_not_found(commit_immediately=True)
        return self

    def as_fhir(self):
        d = {'resourceType': 'Questionnaire'}
        if self.identifiers.count():
            d['identifier'] = []
        for i in self.identifiers:
            d['identifier'].append(i.as_fhir())
        if self.status:
            d['status'] = self.status
        if self.item:
            d['item'] = self.item
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, matching on **name** alone (which is
        maintained as an identifier with the matching system value)

        @return: the new or matched Questionnaire

        """
        assert self.name
        i = Identifier(
            _value=self.name,
            system=TRUENTH_QUESTIONNAIRE_CODE_SYSTEM).add_if_not_found(
            commit_immediately=commit_immediately)
        existing = Questionnaire.find_by_identifier(i)
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

        objs = [{'resource': q.as_fhir()} for q in query]
        link = {
            'rel': 'self', 'href': url_for(
                'questionnaire_api.questionnaire_list', _external=True)}
        return bundle_results(elements=objs, links=[link])

    @classmethod
    def questionnaire_codes(cls):
        questionnaire_identifiers = Identifier.query.join(QuestionnaireIdentifier).filter(
            Identifier.system == TRUENTH_QUESTIONNAIRE_CODE_SYSTEM
        )
        values = {qi.value for qi in questionnaire_identifiers}
        return values

    def questionnaire_code_map(self):
        """Map of Questionnaire codes to corresponding option text"""

        code_text_map = {}
        questionnaire_fhir = self.as_fhir()
        for question in questionnaire_fhir.get('item', ()):
            for option in question.get('option', ()):
                if 'valueCoding' not in option:
                    continue

                code = option['valueCoding']['code']
                text = option['valueCoding']['display']
                code_text_map[code] = text

        return code_text_map


class QuestionnaireIdentifier(db.Model):
    """link table for questionnaire : n identifiers"""
    __tablename__ = 'questionnaire_identifiers'
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.ForeignKey(
        'questionnaires.id', ondelete='cascade'), nullable=False)
    identifier_id = db.Column(db.ForeignKey(
        'identifiers.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint(
        'questionnaire_id', 'identifier_id',
        name='_questionnaire_identifier'),)
