"""Questionnaire Bank module"""
from sqlalchemy import UniqueConstraint

from ..database import db
from .organization import OrgTree
from .questionnaire import Questionnaire
from .reference import Reference


class QuestionnaireBank(db.Model):
    __tablename__ = 'questionnaire_banks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    questionnaires = db.relationship(
        'QuestionnaireBankQuestionnaire',
        back_populates='questionnaire_bank',
        order_by="QuestionnaireBankQuestionnaire.rank")

    # Currently using organizations to associate which questionnaire
    # bank to give to a user.
    organization_id = db.Column(
        db.ForeignKey('organizations.id'), nullable=False)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "QuestionnaireBank {0.id} {0.name}".format(self)

    @classmethod
    def from_json(cls, data):
        instance = cls()
        instance.update_from_json(data)
        return instance

    def update_from_json(self, data):
        self.name = data['name']
        self.organization_id = Reference.parse(
            data['organization']).id
        self.add_if_not_found(commit_immediately=True)
        for q in data['questionnaires']:
            questionnaire = QuestionnaireBankQuestionnaire.from_fhir(
                q)
            questionnaire.questionnaire_bank_id = self.id
            questionnaire = questionnaire.add_if_not_found(True)

    def as_json(self):
        d = {}
        d['resourceType'] = 'QuestionnaireBank'
        d['name'] = self.name
        d['organization'] = Reference.organization(
            self.organization_id).as_fhir()
        d['questionnaires'] = [q.as_fhir() for q in self.questionnaires]
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, adds new if not found.

        @return: the new or matched QuestionnaireBank

        """
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

    @staticmethod
    def q_for_user(user):
        """Lookup and return all questionnaires for the given user

        QuestionnaireBanks are associated with a user through the top
        level organization affiliation.

        :return: list of QuestionnaireBankQuestionnaire objects for given user

        """
        qs = []
        OT = OrgTree()
        for org in user.organizations:
            # Only top level orgs named in associations w/ QuestionnairBanks
            top = OT.find(org.id).top_level()
            qb = QuestionnaireBank.query.filter_by(organization_id=top).first()
            if qb:
                qs += [q for q in qb.questionnaires]
        return qs


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

    questionnaire = db.relationship('Questionnaire')
    questionnaire_bank = db.relationship('QuestionnaireBank')

    __table_args__ = (
        UniqueConstraint(
            questionnaire_bank_id, questionnaire_id,
            name='_questionnaire_bank_questionnaire'),
        UniqueConstraint(
            questionnaire_id, rank,
            name='_questionnaire_bank_questionnaire_rank')
    )

    def __str__(self):
        """Print friendly format for logging, etc."""
        return ("QuestionnaireBankQuestionnaire "
                "{0.questionnaire_bank_id}:{0.questionnaire_id}".format(self))

    @property
    def title(self):
        """Easy access to linked questionnaire `title`"""
        return self.questionnaire.title

    @classmethod
    def from_fhir(cls, data):
        """Instantiate from persisted form

        NB - the questionnaire_bank_id is NOT expected, as it's defined
        by nesting in site_persistence

        """
        instance = cls()
        instance.questionnaire_id = Reference.parse(data['questionnaire']).id
        instance.days_till_due = data['days_till_due']
        instance.days_till_overdue = data['days_till_overdue']
        instance.rank = data['rank']
        return instance

    def as_fhir(self):
        d = {}
        d['questionnaire'] = Reference.questionnaire(self.title).as_fhir()
        for k in ('rank', 'days_till_due', 'days_till_overdue'):
            if getattr(self, k, None):
                d[k] = getattr(self, k)
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
            questionnaire_id=self.questionnaire_id,
            days_till_due=self.days_till_due,
            days_till_overdue=self.days_till_overdue,
            rank=self.rank).first()
        if not existing:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        else:
            self.id = existing.id
        self = db.session.merge(self)
        return self
