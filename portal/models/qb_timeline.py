from datetime import datetime, MAXYEAR

from ..trace import trace
from ..database import db
from .assessment_status import OverallStatus
from .questionnaire_bank import QuestionnaireBank, QBD, qbs_by_rp
from .user_consent import consent_withdrawal_dates


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


system_trigger = datetime(2015, 1, 1, 12, 0, 0)
"""A consistent point in time for date comparisons with relative deltas"""


def ordered_rp_qbs(rp_id):
    """Generator to yield ordered qbs by research protocol alone"""
    # to order, need a somewhat arbitrary date as a fake trigger
    baselines = qbs_by_rp(rp_id, 'baseline')
    if len(baselines) != 1:
        raise RuntimeError(
            "Expect exactly one QB for baseline by rp {}".format(rp_id))
    baseline = baselines[0]
    if baseline not in db.session:
        baseline = db.session.merge(baseline, load=False)
    start = baseline.calculated_start(
        as_of_date=system_trigger, trigger_date=system_trigger)
    yield start

    qbs_by_start = {}
    recurring = qbs_by_rp(rp_id, 'recurring')
    for qb in recurring:
        if qb not in db.session:
            qb = db.session.merge(qb, load=False)

        for qbd in qb.recurring_starts(system_trigger):
            qbs_by_start[qbd.relative_start] = qbd

    # continue to yield in order
    for start_date in sorted(qbs_by_start.keys()):
        yield qbs_by_start[start_date]


def calc_and_adjust_start(user, qbd, initial_trigger):
    """Calculate correct start for user on given QBD

    A QBD is initially generated with a generic trigger date for
    caching and sorting needs.  This function translates the
    given QBD.relative_start to the users situation.

    :param user: subject user
    :param qbd: QBD with respect to system trigger
    :param initial_trigger: datetime value used in initial QBD calculation

    :returns adjusted `relative_start` for user

    """
    users_trigger = qbd.questionnaire_bank.trigger_date(user)
    if initial_trigger > users_trigger:
        raise RuntimeError(
            "user {} has unexpected trigger date before system value".format(
                user.id))

    delta = users_trigger - initial_trigger
    return qbd.relative_start + delta


max_sort_time = datetime(year=MAXYEAR, month=12, day=31)


def second_null_safe_datetime(x):
    """datetime sort accessor treats None as far off in the future"""
    if not x[1]:
        return max_sort_time
    return x[1]


def ordered_qbs(user):
    """Generator to yield ordered qbs for a user

    This does NOT consider user submissions, simply returns
    the ordered list up till user withdraws or runs out of QBs.

    This does NOT include the indefinite classification, as it
    plays by a different set of rules.

    :param user: the user to lookup
    :returns: QBD named tuple for each (QB, iteration)

    """

    # bootstrap problem - don't know initial `as_of_date` w/o a QB
    # use consent date as best guess.
    consent_date, withdrawal_date = consent_withdrawal_dates(user)
    if not consent_date:
        # TODO: are there use cases w/o a consent, yet a valid trigger_date?
        raise StopIteration

    # Zero to one RP makes things significantly easier - otherwise
    # swap in a strategy that can work with the change.
    rps = set()
    for org in user.organizations:
        for r in org.rps_w_retired():
            rps.add(r)

    if len(rps) > 1:
        # With a multiple RPs, move in lock step, determine when to switch.
        sorted_rps = sorted(
            list(rps), key=second_null_safe_datetime, reverse=True)

        # Start with oldest (current) till it's time to progress (next)
        current_rp, current_retired = sorted_rps.pop()
        current_qbds = ordered_rp_qbs(current_rp.id)
        next_rp, next_retired = sorted_rps.pop()
        next_qbds = ordered_rp_qbs(next_rp.id)

        if sorted_rps:
            raise ValueError("can't cope with > 2 RPs at this time")

        while True:
            # Advance both in sync while both are defined
            current_qbd = next(current_qbds)
            if next_qbds:
                next_qbd = next(next_qbds)
            users_start = calc_and_adjust_start(
                user=user, qbd=current_qbd, initial_trigger=system_trigger)

            # if there's still a next and current retired before the user's
            # start, switch over
            # TODO don't switch yet if user submitted any results for this qbd
            if next_qbds and current_retired < users_start:
                current_qbds = next_qbds
                current_qbd, current_retired = next_qbd, next_retired
                next_qbds, next_retired = None, None
                users_start = calc_and_adjust_start(
                    user=user, qbd=current_qbd,
                    initial_trigger=system_trigger)

            # done if user withdrew before the next start
            if withdrawal_date and withdrawal_date < users_start:
                break

            adjusted = current_qbd._replace(relative_start=users_start)
            yield adjusted

    if len(rps) == 1:
        # With a single RP, just need to adjust the start to fit
        # this user
        rp, _ = rps.pop()
        qbds_by_rp = ordered_rp_qbs(rp.id)
        while True:
            qbd = next(qbds_by_rp)
            users_start = calc_and_adjust_start(
                user=user, qbd=qbd, initial_trigger=system_trigger)

            # done if user withdrew before the next start
            if withdrawal_date and withdrawal_date < users_start:
                break

            adjusted = qbd._replace(relative_start=users_start)
            yield adjusted


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
