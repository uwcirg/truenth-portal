"""Recur module"""
from sqlalchemy import UniqueConstraint

from ..database import db
from ..date_tools import RelativeDelta


class Recur(db.Model):
    """Captures parameters needed for a recurring task

    NB - an external context defines the initial launch point
    aka `trigger_date` and is NOT part of this structure.

    """
    __tablename__ = 'recurs'
    id = db.Column(db.Integer, primary_key=True)
    start = db.Column(
        db.Text, nullable=False,
        doc=("'relativedelta' value (i.e. {\"months\": 3, \"days\": -14}) "
             " from trigger date to start recurrence"))
    cycle_length = db.Column(
        db.Text, nullable=False,
        doc="'relativedelta' value till repeat of the recurrence, from start")
    termination = db.Column(
        db.Text, nullable=True,
        doc=("optional 'relativedelta' value till termination of recurrence, "
             "from trigger date"))

    __table_args__ = (
        UniqueConstraint(
            start, cycle_length, termination,
            name='_unique_recur'),
    )

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        @return: the new or matched Recur

        """
        query = Recur.query.filter(
            Recur.start == self.start,
            Recur.cycle_length == self.cycle_length,
            Recur.termination == self.termination)

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
                'start', 'cycle_length', 'termination'):
            setattr(instance, field, data.get(field))
            if data.get(field):
                RelativeDelta.validate(data.get(field))
        return instance.add_if_not_found()

    def as_json(self):
        d = {}
        for field in (
                'start', 'cycle_length', 'termination'):
            if getattr(self, field):
                d[field] = getattr(self, field)
        return d

    def active_interval_start(self, trigger_date, as_of_date):
        """Return two tuple (start, iteration_count)

        Return UTC datetime for active recurrence start and the
        iteration_count if it applies, or (None, None) if N/A

        :param trigger_date: The UTC datetime defining external context
            launch point of the study or procedure date, etc.

        :param as_of_date: The UTC datetime defining the current point in time
            against which to compare iterations to find the relevant cycle.

        :return: UTC datetime for active recurrence start and None or the
            iteration_count if it applies, if the time range is valid.  (None,
            None) if the recurrence has either expired (beyond termination) or
            has yet to begin (prior to start).

        """
        assert as_of_date
        start_date = trigger_date + RelativeDelta(self.start)
        termination = (
            trigger_date + RelativeDelta(self.termination) if
            self.termination else None)

        if as_of_date < start_date:
            # Has yet to begin
            return (None, None)
        if termination and as_of_date > termination:
            # Recurrence terminated
            return (None, None)

        # Still here implies we're in a valid period - find the current
        # and return its effective start date
        assert (as_of_date + RelativeDelta(self.cycle_length) > as_of_date)

        effective_start = start_date
        iteration_count = 0
        while True:
            if effective_start + RelativeDelta(self.cycle_length) < as_of_date:
                effective_start += RelativeDelta(self.cycle_length)
                iteration_count += 1
            else:
                return (effective_start, iteration_count)


class QuestionnaireBankRecur(db.Model):
    """Link table for QB -> Recur"""
    __tablename__ = 'questionnaire_bank_recurs'
    id = db.Column(db.Integer(), primary_key=True)
    questionnaire_bank_id = db.Column(
        db.Integer(), db.ForeignKey(
            'questionnaire_banks.id', ondelete='CASCADE'),
        nullable=False)
    recur_id = db.Column(db.Integer(), db.ForeignKey(
        'recurs.id', ondelete='CASCADE'), nullable=False)
    iteration_count = db.Column(
        db.Integer(), server_default="0", nullable=False)

    __table_args__ = (
        UniqueConstraint(
            questionnaire_bank_id, recur_id, iteration_count,
            name='_questionnaire_bank_recure'),
    )

    def __str__(self):
        """Print friendly format for logging, etc."""
        return ("QuestionnaireBankRecur "
                "{0.questionnaire_bank_id}:"
                "{0.recur_id} {0.iteration_count}".format(self))
