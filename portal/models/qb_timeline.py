from datetime import datetime, MAXYEAR

from ..database import db
from ..date_tools import RelativeDelta
from .assessment_status import OverallStatus
from .questionnaire_bank import qbs_by_rp, qbs_by_intervention
from .questionnaire_response import QNR_results
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


def ordered_intervention_qbs(user):
    """Generator to yield ordered qbs by intervention"""
    # to order, need a somewhat arbitrary date as a fake trigger
    baselines = qbs_by_intervention(user, 'baseline')
    if len(baselines) != 1:
        raise RuntimeError(
            "Expect exactly one QB for baseline by intervention")
    baseline = baselines[0]
    if baseline not in db.session:
        baseline = db.session.merge(baseline, load=False)
    start = baseline.calculated_start(
        as_of_date=system_trigger, trigger_date=system_trigger)
    yield start

    qbs_by_start = {}
    recurring = qbs_by_intervention(user, 'recurring')
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
        # RP switch is delayed if user submitted any results for the then
        # active QB on the RP active at that time.
        user_qnrs = QNR_results(user)

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
            # start, switch over *unless* user submitted a matching QNR
            if (next_qbds and current_retired < users_start and
                    not user_qnrs.earliest_result(
                        qb_id=current_qbd.questionnaire_bank.id,
                        iteration=current_qbd.iteration)):
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

    elif len(rps) == 1:
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

    else:
        # Neither RP case hit, try intervention associated QBs
        iqbds = ordered_intervention_qbs(user)
        while True:
            qbd = next(iqbds)
            users_start = calc_and_adjust_start(
                user=user, qbd=qbd, initial_trigger=system_trigger)

            adjusted = qbd._replace(relative_start=users_start)
            yield adjusted

def update_users_QBT(user, invalidate_existing=False):
    """Populate the QBT rows for given user

    :param user: the user to add QBT rows for
    :param invalidate_existing: set true to wipe any current rows first

    """
    if invalidate_existing:
        QBT.query.filter(QBT.user_id == user.id).delete()

    # don't expect any rows at this point for user - sanity check
    if QBT.query.filter(QBT.user_id == user.id).count():
        raise RuntimeError("Found unexpected QBT rows for {}".format(
            user))

    # Create time line for user, from initial trigger date
    qb_generator = ordered_qbs(user)
    user_qbrs = QNR_results(user)

    # As we move forward, capture state at each time point

    pending_qbts = []
    for qbd in qb_generator:
        kwargs = {
            "user_id": user.id, "qb_id": qbd.questionnaire_bank.id,
            "qb_iteration": qbd.iteration}
        start = qbd.relative_start
        # Always add start (due)
        pending_qbts.append(QBT(at=start, status='due', **kwargs))

        expired_date = start + RelativeDelta(qbd.questionnaire_bank.expired)
        overdue_date = None
        if qbd.questionnaire_bank.overdue:  # not all qbs define overdue
            overdue_date = start + RelativeDelta(
                qbd.questionnaire_bank.overdue)
        partial_date = user_qbrs.earliest_result(
            qbd.questionnaire_bank.id, qbd.iteration)
        include_overdue, include_expired = True, True
        complete_date, expired_as_partial = None, False

        # If we have at least one result for this (QB, iteration):
        if partial_date:
            if overdue_date and partial_date < overdue_date:
                include_overdue = False
            if partial_date < expired_date:
                pending_qbts.append(QBT(
                    at=partial_date, status='in_progress', **kwargs))
                # Without subsequent results, expired will become partial
                include_expired = False
                expired_as_partial = True
            else:
                pending_qbts.append(QBT(
                    at=partial_date, status='partially_completed', **kwargs))

            complete_date = user_qbrs.completed_date(
                qbd.questionnaire_bank.id, qbd.iteration)
            if complete_date:
                pending_qbts.append(QBT(
                    at=complete_date, status='completed',
                    **kwargs))
                if complete_date < expired_date:
                    include_expired = False
                    expired_as_partial = False

        if include_overdue and overdue_date:
            pending_qbts.append(QBT(
                at=overdue_date, status='overdue', **kwargs))

        if expired_as_partial:
            pending_qbts.append(QBT(
                at=expired_date, status="partially_completed", **kwargs))
            if include_expired:
                raise RuntimeError("conflicting state")

        if include_expired:
            pending_qbts.append(QBT(
                at=expired_date, status='expired', **kwargs))

    # If user withdrew from study - remove any rows post withdrawal
    _, withdrawal_date = consent_withdrawal_dates(user)
    if withdrawal_date:
        store_rows = [qbt for qbt in pending_qbts if qbt.at < withdrawal_date]
        db.session.add_all(store_rows)
    else:
        db.session.add_all(pending_qbts)

    db.session.commit()
