"""Questionnaire Bank module"""
from flask import url_for
from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import ENUM

from ..database import db
from ..date_tools import FHIR_datetime
from .questionnaire import Questionnaire
from .recur import Recur
from .reference import Reference


classification_types = ('baseline', 'recurring', 'indefinite')
classification_types_enum = ENUM(
    *classification_types, name='classification_enum', create_type=False)


class QuestionnaireBank(db.Model):
    __tablename__ = 'questionnaire_banks'
    __table_args__ = (
        CheckConstraint('NOT(organization_id IS NULL AND '
                            'intervention_id IS NULL) '
                        'AND NOT(organization_id IS NOT NULL AND '
                                'intervention_id IS NOT NULL)'),
        )
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    classification = db.Column(
        'classification', classification_types_enum,
        server_default='baseline', nullable=False)
    questionnaires = db.relationship(
        'QuestionnaireBankQuestionnaire',
        back_populates='questionnaire_bank',
        order_by="QuestionnaireBankQuestionnaire.rank")

    # QuestionnaireBank is associated with an Organization OR an Intervention,
    # either of which dictate whether it's given to a User
    organization_id = db.Column(
        db.ForeignKey('organizations.id'), nullable=True)
    intervention_id = db.Column(
        db.ForeignKey('interventions.id'), nullable=True)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "QuestionnaireBank {0.id} {0.name} {0.classification}".format(
            self)

    @classmethod
    def from_json(cls, data):
        instance = cls()
        return instance.update_from_json(data)

    def update_from_json(self, data):
        self.name = data['name']
        if 'classification' in data:
            self.classification = data['classification']
        self.organization_id = Reference.parse(
            data['organization']).id
        self = self.add_if_not_found(commit_immediately=True)
        qs_named = set()
        for q in data['questionnaires']:
            questionnaire = QuestionnaireBankQuestionnaire.from_json(
                q)
            questionnaire.questionnaire_bank_id = self.id
            questionnaire = questionnaire.add_if_not_found(True)
            if questionnaire not in self.questionnaires:
                self.questionnaires.append(questionnaire)
            qs_named.add(questionnaire)

        # remove any stale
        for unwanted in set(self.questionnaires) - qs_named:
            self.questionnaires.remove(unwanted)
            db.session.delete(unwanted)

        return self

    def as_json(self):
        d = {}
        d['resourceType'] = 'QuestionnaireBank'
        d['name'] = self.name
        d['classification'] = self.classification
        d['organization'] = Reference.organization(
            self.organization_id).as_fhir()
        d['questionnaires'] = [q.as_json() for q in self.questionnaires]
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, adds new if not found.

        @return: the new or matched QuestionnaireBank

        """
        assert self.name
        existing = QuestionnaireBank.query.filter_by(
            name=self.name).first()
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
        """Generate a FHIR bundle of existing questionnaire banks ordered by ID

        If limit_to_ids is defined, only return the matching set, otherwise
        all questionnaire banks found.

        """
        query = QuestionnaireBank.query.order_by(QuestionnaireBank.id)
        if limit_to_ids:
            query = query.filter(QuestionnaireBank.id.in_(limit_to_ids))

        objs = [q.as_json() for q in query]

        bundle = {
            'resourceType': 'Bundle',
            'updated': FHIR_datetime.now(),
            'total': len(objs),
            'type': 'searchset',
            'link': {
                'rel': 'self',
                'href': url_for(
                    'assessment_engine_api.questionnaire_bank_list',
                    _external=True),
            },
            'entry': objs,
        }
        return bundle


class QuestionnaireBankQuestionnaire(db.Model):
    """link table for n:n association between Questionnaires and Banks"""
    __tablename__ = 'questionnaire_bank_questionnaires'
    id = db.Column(db.Integer(), primary_key=True)
    questionnaire_bank_id = db.Column(db.Integer(), db.ForeignKey(
        'questionnaire_banks.id', ondelete='CASCADE'), nullable=False)
    questionnaire_id = db.Column(db.Integer(), db.ForeignKey(
        'questionnaires.id', ondelete='CASCADE'), nullable=False)
    days_till_due = db.Column(db.Integer, nullable=False)
    days_till_overdue = db.Column(db.Integer, nullable=False)
    rank = db.Column(db.Integer, nullable=False)

    questionnaire = db.relationship(Questionnaire)
    questionnaire_bank = db.relationship('QuestionnaireBank')
    recurs = db.relationship(
        Recur, secondary='questionnaire_bank_questionnaire_recurs')

    __table_args__ = (
        UniqueConstraint(
            questionnaire_bank_id, questionnaire_id,
            name='_questionnaire_bank_questionnaire'),
        UniqueConstraint(
            questionnaire_bank_id, rank,
            name='_questionnaire_bank_questionnaire_rank')
    )

    def __str__(self):
        """Print friendly format for logging, etc."""
        return ("QuestionnaireBankQuestionnaire "
                "{0.questionnaire_bank_id}:{0.questionnaire_id}".format(self))

    @property
    def name(self):
        """Easy access to linked questionnaire `name`"""
        return self.questionnaire.name

    @classmethod
    def from_json(cls, data):
        """Instantiate from persisted form

        NB - the questionnaire_bank_id is NOT expected, as it's defined
        by nesting in site_persistence

        """
        instance = cls()
        instance.questionnaire_id = Reference.parse(data['questionnaire']).id
        instance.days_till_due = data['days_till_due']
        instance.days_till_overdue = data['days_till_overdue']
        instance.rank = data['rank']
        for r in data.get('recurs', []):
            instance.recurs.append(Recur.from_json(r).add_if_not_found())
        return instance

    def as_json(self):
        d = {}
        d['questionnaire'] = Reference.questionnaire(self.name).as_fhir()
        for k in ('rank', 'days_till_due', 'days_till_overdue'):
            d[k] = getattr(self, k)
        d['recurs'] = [r.as_json() for r in self.recurs]
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, adds new if not found.

        @return: the new or matched QuestionnaireBankQuestionnaire

        """
        assert(self.questionnaire_id)
        assert(self.questionnaire_bank_id)
        if self in db.session:
            assert self.id
            return self
        existing = QuestionnaireBankQuestionnaire.query.filter_by(
                    questionnaire_bank_id=self.questionnaire_bank_id,
                    questionnaire_id=self.questionnaire_id).first()
        if not existing:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        else:
            self.id = existing.id
        self = db.session.merge(self)
        return self
