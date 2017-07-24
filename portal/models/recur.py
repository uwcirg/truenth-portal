"""Recur module"""
from datetime import datetime, timedelta
from sqlalchemy import UniqueConstraint

from ..database import db


class Recur(db.Model):
    """Captures parameters needed for a recurring task

    NB - an external context defines the initial launch point
    and is NOT part of this structure, such as the date
    a user signed a consent agreement.  (by design, makes testing
    reasonable as the start date can easily be adjusted)

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
        doc="optional termination of recurrance; days from initial lauch")

    __table_args__ = (
        UniqueConstraint(
            days_to_start, days_in_cycle, days_till_termination,
            name='_unique_recur'),
    )

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        @return: the new or matched Recur

        """
        query = Recur.query.filter(
            Recur.days_to_start == self.days_to_start,
            Recur.days_in_cycle == self.days_in_cycle,
            Recur.days_in_cycle == self.days_in_cycle)

        if query.count():
            result = query.one()
            self.id = result.id
        else:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        self = db.session.merge(self)
        return self

    @classmethod
    def from_json(cls, data):
        instance = cls()
        for field in (
                'days_to_start', 'days_in_cycle', 'days_till_termination'):
            setattr(instance, field, data.get(field))
        return instance.add_if_not_found()

    def as_json(self):
        d = {}
        for field in (
                'days_to_start', 'days_in_cycle', 'days_till_termination'):
            if getattr(self, field):
                d[field] = getattr(self, field)
        return d

    def active_interval_start(self, start):
        """Return datetime for active recurrance start or None

        :param start: The UTC datetime defining external context launch point,
            such as the date of consent with an organization for questionnaires

        :return: UTC datetime for active recurrance start or None if
            the recurrance has either expired (beyond days_till_termination) or
            has yet to begin (prior to days_to_start)

        """
        now = datetime.utcnow()
        start_date = start + timedelta(self.days_to_start)
        termination = (
            start + timedelta(self.days_till_termination) if
            self.days_till_termination else None)

        if now < start_date:
            # Has yet to begin
            return None
        if termination and now > termination:
            # Recurrance terminated
            return None

        # Still here implies we're in a valid period - find the current
        # and return its effective start date
        effective_start = start_date
        while True:
            if effective_start + timedelta(self.days_in_cycle) < now:
                effective_start += timedelta(self.days_in_cycle)
            else:
                return effective_start


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
