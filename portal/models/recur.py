"""Recur module"""
from sqlalchemy import UniqueConstraint

from ..database import db


class Recur(db.Model):
    """Captures parameters needed for a recurring task

    NB - an external context defines the initial launch point
    and is NOT part of this structure, such as the date
    a user signed a consent agreement.  (by design, makes testing
    possible as the start date can easily be adjusted)

    """
    __tablename__ = 'recurs'
    id = db.Column(db.Integer, primary_key=True)
    days_to_start = db.Column(
        db.Integer, nullable=False,
        doc="Days from initial launch event to start recurrance")
    days_in_cycle = db.Column(
        db.Integer, nullable=False,
        doc="Days till repeat of the recurrance")
    days_till_termination = db.Column(
        db.Integer, nullable=True,
        doc="termination of recurrance; days from initial lauch")

    @classmethod
    def from_fhir(cls, data):
        instance = cls()
        for field in (
                'days_to_start', 'days_in_cycle', 'days_till_termination'):
            setattr(instance, field, data.get(field))
        return instance

    def as_fhir(self):
        d = {}
        for field in (
                'days_to_start', 'days_in_cycle', 'days_till_termination'):
            d[field] = getattr(self, field, None)
        return d


class QuestionnaireBankQuestionnaireRecur(db.Model):
    """Link table for QBQ -> Recur"""
    __tablename__ = 'questionnaire_bank_questionnaire_recurs'
    id = db.Column(db.Integer(), primary_key=True)
    questionnaire_bank_questionnaire_id = db.Column(
        db.Integer(), db.ForeignKey(
            'questionnaire_bank_questionnaires.id', ondelete='CASCADE'),
        nullable=False)
    recur_id = db.Column(db.Integer(), db.ForeignKey(
        'recurs.id', ondelete='CASCADE'), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            questionnaire_bank_questionnaire_id, recur_id,
            name='_questionnaire_bank_questionnaire_recure'),
    )

    def __str__(self):
        """Print friendly format for logging, etc."""
        return ("QuestionnaireBankQuestionnaireRecur "
                "{0.questionnaire_bank_questionnaire_id}:"
                "{0.recur_id}".format(self))
