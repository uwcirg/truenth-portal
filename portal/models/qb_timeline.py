from datetime import datetime, MAXYEAR

from .assessment_status import OverallStatus
from .questionnaire_bank import QuestionnaireBank, QBD
from ..trace import trace
from ..database import db


class QBT(db.Model):
    """Effectively a view, to simplify QB status lookups over time

    A user has a number of QBT rows, at least one for each questionnaire
    bank that has been due for the user, or will be in the future.

    The following events would invalidate the respective rows (delete
    said rows to invalidate):
     - user's trigger date changed (consent or new procedure)
     - user submits a QuestionnaireResponse
     - the definition of a QB or an organization's research protocol

    The table is populated up to the next known event for a user.  If a
    future date isn't found, that user's data is due for update.

    """
    __tablename__ = 'questionnaire_bank_timeline'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey(
        'users.id', ondelete='cascade'), nullable=False)
    at = db.Column(
        db.DateTime, nullable=False,
        doc="initial date time for state of row")
    qb_id = db.Column(db.ForeignKey(
        'questionnaire_banks.id', ondelete='cascade'), nullable=True)
    qb_iteration = db.Column(db.Integer, nullable=True)
    _status = db.Column('status', db.Text, nullable=False)

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = getattr(OverallStatus, value).name


def ordered_qbs(user):
    """Generator to yield ordered qbs for a user

    This does NOT consider user submissions, simply returns
    the ordered list up till user withdraws or runs out of QBs.

    This does NOT include the indefinite classification, as it
    plays by a different set of rules.

    :param user: the user to lookup
    :returns: QBD named tuple for each (QB, iteration)

    """
    # Starts with baseline
    as_of = datetime.utcnow()
    baseline = QuestionnaireBank.qbs_for_user(
        user, as_of_date=as_of, classification='baseline')
    if not baseline:
        raise StopIteration
    if len(baseline) != 1:
        raise RuntimeError('unexpected multiple baselines')

    trigger_date = baseline[0].trigger_date(user)
    if not trigger_date:
        raise StopIteration
    start = baseline[0].calculated_start(
        as_of_date=as_of, trigger_date=trigger_date)
    yield QBD(
        relative_start=start, iteration=None, recur=None,
        questionnaire_bank=baseline[0])

    # Trigger date sometimes changes by classification - force fresh lookup
    trigger_date = None

    # Move on to recurring - sort requires pre-fetch as they often overlap
    qbs_by_start = {}

    # Zero to one RP makes things significantly easier - otherwise
    # swap in a strategy that can work with the change.
    rps = QuestionnaireBank.current_rps(user, as_of_date=None)
    if len(rps) > 1:
        raise NotImplementedError("need strategy for changing RPs")

    # Users have org or intervention associated QBs
    org_recurring = QuestionnaireBank.qbs_by_org(
        user, classification='recurring', as_of_date=None)
    intervention_recurring = QuestionnaireBank.qbs_by_intervention(
        user, classification='recurring')
    for qb in org_recurring + intervention_recurring:

        # acquire trigger for this classification if not defined
        trigger_date = trigger_date if trigger_date else qb.trigger_date(user)

        for qbd in qb.recurring_starts(trigger_date):
            qbs_by_start[qbd.relative_start] = qbd

    # continue to yield in order
    withdrawal_date = QuestionnaireBank.withdrawal_date(user)
    for start_date in sorted(qbs_by_start.keys()):
        if withdrawal_date and withdrawal_date < start_date:
            break
        yield qbs_by_start[start_date]


def update_users_QBT(user, invalidate_existing=False):
    """Populate the QBT rows up till one future event for given user

    :param user: the user to add QBT rows for
    :param invalidate_existing: set true to wipe any current rows first

    """
    def last_row(qb_id, iteration, start, status):
        """add last row for user and commit"""
        last = QBT(
            user_id=user.id, qb_id=qb_id, qb_iteration=iteration, status=status)
        if not start:
            # no start implies we have no future plans for user
            start = datetime(year=MAXYEAR, month=12, day=31)
        last.start = start
        db.session.add(last)
        db.session.commit()

    if invalidate_existing:
        QBT.query.filter(QBT.user_id == user.id).delete()

    # Create time line for user, from initial trigger date
    now = datetime.utcnow()
    baseline = QuestionnaireBank.qbs_for_user(
        user, classification='baseline', as_of_date=now)

    trigger_date = baseline[0].trigger_date(user)

    if not trigger_date:
        trace("no baseline trigger date, can't continue")
        last_row(qb_id=None, iteration=None, status='expired')
        return

    qb = baseline[0]
    qbd_start = qb.calculated_start(trigger_date=trigger_date, as_of_date=now)
    due = qb.calculated_due(trigger_date=trigger_date, as_of_date=now)
    initial = QBT(
        user_id=user.id, qb_id=qb.id, iteration=None, status='due',
        start=due or qbd_start.relative_start)
    db.session.add(initial)

    # If user submitted a response for the QB, the authored date
    # changed the status
    in_progress = QuestionnaireBank.submitted_qbs(user=user, classification=baseline)
