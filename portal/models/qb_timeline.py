from collections import namedtuple
from datetime import MAXYEAR, datetime
from time import sleep

from dateutil.relativedelta import relativedelta
from flask import current_app
import redis
from redis.exceptions import ConnectionError
from sqlalchemy.types import Enum as SQLA_Enum
from werkzeug.exceptions import BadRequest

from ..audit import auditable_event
from ..database import db
from ..date_tools import FHIR_datetime, RelativeDelta
from ..dogpile_cache import dogpile_cache
from ..set_tools import left_center_right
from ..timeout_lock import TimeoutLock
from ..trace import trace
from .overall_status import OverallStatus
from .qbd import QBD
from .questionnaire_bank import (
    qbs_by_intervention,
    qbs_by_rp,
    trigger_date,
    visit_name,
)
from .questionnaire_response import QNR_results, QuestionnaireResponse
from .research_protocol import ResearchProtocol
from .role import ROLE
from .user import User
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
    __tablename__ = 'qb_timeline'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey(
        'users.id', ondelete='cascade'), nullable=False)
    at = db.Column(
        db.DateTime, nullable=False, index=True,
        doc="initial date time for state of row")
    qb_id = db.Column(db.ForeignKey(
        'questionnaire_banks.id', ondelete='cascade'), nullable=True)
    qb_recur_id = db.Column(db.ForeignKey(
        'recurs.id', ondelete='cascade'), nullable=True)
    qb_iteration = db.Column(db.Integer, nullable=True)
    status = db.Column(SQLA_Enum(OverallStatus), nullable=False, index=True)

    def qbd(self):
        """Generate and return a QBD instance from self data"""
        return QBD(
            relative_start=self.at, iteration=self.qb_iteration,
            recur_id=self.qb_recur_id, qb_id=self.qb_id)


class AtOrderedList(list):
    """Specialize ``list`` to maintain insertion order and ``at`` attribute

    When building up QBTs for a user, we need to maintain both order and
    sort by the ``QBT.at`` attribute.  As there are rows with identical ``at``
    values, it can't simply be sorted by a field, as insertion order matters
    in the case of a tie (as say the ``due`` status needs to precede a
    ``completed``, which does happen with paper entry).

    As the build order matters, continue to add QBTs to the end of the list,
    taking special care to insert those with earlier ``at`` values in
    the correct place.  Two or more identical ``at`` values should result
    in the latest addition following preexisting.

    """

    def append(self, value):
        """Maintain order by appending or inserting as needed

        If the given value.at is > current_end.at, append to end.
        Otherwise, walk backwards till the new can be inserted
        so the list remains ordered by the 'at' attribute, with
        new matching values following existing

        """
        if not self.__len__():
            return super(AtOrderedList, self).append(value)

        # Expecting to build in order; common case new value
        # lands at end.
        if self[-1].at <= value.at:
            return super(AtOrderedList, self).append(value)

        # Otherwise, walk backwards till new value < existing
        for i, e in reversed(list(enumerate(self))):
            if i > 0:
                # If not at start and previous is also greater
                # than new, continue to walk backwards
                if self[i-1].at > value.at:
                    continue
            if e.at > value.at:
                return self.insert(i, value)

        raise ValueError("still here?")


def ordered_rp_qbs(rp_id, trigger_date):
    """Generator to yield ordered qbs by research protocol alone"""
    baselines = qbs_by_rp(rp_id, 'baseline')
    if len(baselines) != 1:
        raise RuntimeError(
            "Expect exactly one QB for baseline by rp {}".format(rp_id))
    baseline = baselines[0]
    if baseline not in db.session:
        baseline = db.session.merge(baseline, load=False)
    start = baseline.calculated_start(trigger_date=trigger_date)
    yield start

    qbs_by_start = {}
    recurring = qbs_by_rp(rp_id, 'recurring')
    for qb in recurring:
        if qb not in db.session:
            qb = db.session.merge(qb, load=False)

        for qbd in qb.recurring_starts(trigger_date):
            qbs_by_start[qbd.relative_start] = qbd

    # continue to yield in order
    trace("found {} total recurring QBs".format(len(qbs_by_start)))
    for start_date in sorted(qbs_by_start.keys()):
        yield qbs_by_start[start_date]


def ordered_intervention_qbs(user, trigger_date):
    """Generator to yield ordered qbs by intervention"""
    baselines = qbs_by_intervention(user, 'baseline')
    if not baselines:
        return
    if len(baselines) > 1:
        raise RuntimeError(
            "{} has {} baselines by intervention (expected ONE)".format(
                user, len(baselines)))
    baseline = baselines[0]
    if baseline not in db.session:
        baseline = db.session.merge(baseline, load=False)
    start = baseline.calculated_start(trigger_date=trigger_date)
    yield start

    qbs_by_start = {}
    recurring = qbs_by_intervention(user, 'recurring')
    for qb in recurring:
        if qb not in db.session:
            qb = db.session.merge(qb, load=False)

        for qbd in qb.recurring_starts(trigger_date=trigger_date):
            qbs_by_start[qbd.relative_start] = qbd

    # continue to yield in order
    for start_date in sorted(qbs_by_start.keys()):
        yield qbs_by_start[start_date]


def indef_qbs_by_rp(rp_id, trigger_date):
    """Generator to yield ordered `indefinite` qbs by research protocol

    At the moment, only expecting to yield one, but following generator
    pattern to facilitate polymorphic code.

    """
    indefinites = qbs_by_rp(rp_id, 'indefinite')
    for indefinite in indefinites:
        if indefinite not in db.session:
            indefinite = db.session.merge(indefinite, load=False)
        start = indefinite.calculated_start(trigger_date=trigger_date)
        yield start


def indef_intervention_qbs(user, trigger_date):
    """Generator to yield indefinite qbs by intervention"""
    indefinites = qbs_by_intervention(user, 'indefinite')
    for indefinite in indefinites:
        if indefinite not in db.session:
            indefinite = db.session.merge(indefinite, load=False)
        start = indefinite.calculated_start(trigger_date=trigger_date)
        yield start


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
    users_trigger = trigger_date(user, qbd.questionnaire_bank)
    if not users_trigger:
        trace(
            "no valid trigger, default to initial value: {}".format(
                initial_trigger))
        users_trigger = initial_trigger
    if initial_trigger > users_trigger:
        trace(
            "user {} has unexpected trigger date before consent date".format(
                user.id))

    delta = users_trigger - initial_trigger
    if not qbd.relative_start:
        raise RuntimeError("can't adjust without relative_start")
    return qbd.relative_start + delta


def calc_and_adjust_expired(user, qbd, initial_trigger):
    """Calculate correct expired for user on given QBD

    A QBD is initially generated with a generic trigger date for
    caching and sorting needs.  This function translates the
    given QBD.relative_start to the users situation.

    :param user: subject user
    :param qbd: QBD with respect to system trigger
    :param initial_trigger: datetime value used in initial QBD calculation

    :returns adjusted `relative_start` for user

    """
    users_trigger = trigger_date(user, qbd.questionnaire_bank)
    if not users_trigger:
        trace(
            "no valid trigger, default to initial value: {}".format(
                initial_trigger))
        users_trigger = initial_trigger
    if initial_trigger > users_trigger:
        trace(
            "user {} has unexpected trigger date before consent date".format(
                user.id))

    expired = qbd.questionnaire_bank.expired
    delta = users_trigger - initial_trigger + RelativeDelta(expired)
    if not qbd.relative_start:
        raise RuntimeError("can't adjust without relative_start")
    return qbd.relative_start + delta


max_sort_time = datetime(year=MAXYEAR, month=12, day=31)


def second_null_safe_datetime(x):
    """datetime sort accessor treats None as far off in the future"""
    if not x[1]:
        return max_sort_time
    return x[1]


RPD = namedtuple("RPD", ['rp', 'retired', 'qbds'])


def cur_next_rp_gen(user, classification, trigger_date):
    """Generator to manage transitions through research protocols

    Returns a *pair* of research protocol data (RPD) namedtuples,
    one for current (active) RP data, one for the "next".

    :param user: applicable patient
    :param classification: None or 'indefinite' for special handling
    :param trigger_date: patient's initial trigger date

    :yields: cur_RPD, next_RPD

    """
    rps = ResearchProtocol.assigned_to(user)
    sorted_rps = sorted(
        list(rps), key=second_null_safe_datetime, reverse=True)

    def qbds_for_rp(rp, classification, trigger_date):
        if rp is None:
            return None
        if classification == 'indefinite':
            return indef_qbs_by_rp(rp.id, trigger_date=trigger_date)
        return ordered_rp_qbs(rp.id, trigger_date=trigger_date)

    while sorted_rps:
        # Start with oldest RP (current) till it's time to progress (next)
        current_rp, current_retired = sorted_rps.pop()
        if sorted_rps:
            next_rp, next_retired = sorted_rps[-1]
        else:
            next_rp = None
        trace("current RP {}, next RP {}".format(
            current_rp.id, next_rp.id if next_rp else 'None'))

        curRPD = RPD(
            rp=current_rp,
            retired=current_retired,
            qbds=qbds_for_rp(current_rp, classification, trigger_date))
        if next_rp:
            nextRPD = RPD(
                rp=next_rp,
                retired=next_retired,
                qbds=qbds_for_rp(next_rp, classification, trigger_date)
            )
            if curRPD.retired == nextRPD.retired:
                raise ValueError(
                    "Invalid state: multiple RPs w/ same retire date")
        else:
            nextRPD = None
        yield curRPD, nextRPD


def ordered_qbs(user, classification=None):
    """Generator to yield ordered qbs for a user

    This does NOT include the indefinite classification unless requested,
     as it plays by a different set of rules.

    :param user: the user to lookup
    :param classification: set to ``indefinite`` for that special handling
    :returns: QBD for each (QB, iteration, recur)

    """
    if classification == 'indefinite':
        trace("begin ordered_qbds() on `indefinite` classification")
    elif classification is not None:
        raise ValueError(
            "only 'indefinite' or default (None) classifications allowed")

    def nextQBD(qbds_gen):
        """Returns next qbd, user's start and expiration from generator"""
        current_qbd = next(qbds_gen, None)
        if current_qbd is None:
            return None, None, None
        users_start = calc_and_adjust_start(
            user=user, qbd=current_qbd, initial_trigger=td)
        users_expiration = calc_and_adjust_expired(
            user=user, qbd=current_qbd, initial_trigger=td)
        return current_qbd, users_start, users_expiration

    # bootstrap problem - don't know initial `as_of_date` w/o a QB
    # call `trigger_date` w/o QB for best guess.
    td = trigger_date(user=user)
    old_td, withdrawal_date = consent_withdrawal_dates(user)
    if not td:
        if old_td:
            trace("withdrawn user, use previous trigger {}".format(old_td))
            td = old_td
        else:
            trace("no trigger date therefore nothing from ordered_qbds()")
            return

    rp_walker = cur_next_rp_gen(user, classification, td)
    curRPD, nextRPD = next(rp_walker, (None, None))

    if curRPD:
        user_qnrs = QNR_results(user)
        current_qbd, users_start, users_expiration = nextQBD(curRPD.qbds)
        if not current_qbd:
            trace("no current found in initial QBD lookup, bail")
            return
        if nextRPD:
            next_qbd, next_start, next_expiration = nextQBD(nextRPD.qbds)
            skipped_next_start = None
        while True:
            if nextRPD and curRPD.retired < users_expiration:
                # if there's a nextRP and curRP is retired before the
                # user's QB for the curRP expires, we look to transition
                # the user to the nextRP.
                #
                # if however, the user has already posted QNRs for the
                # currentRP one of two things needs to happen:
                #
                #   1. if any of the QNRs are for instruments which
                #      deterministically* demonstrate work on the current
                #      RP has begun, we postpone the transition to the next
                #      RP till the subsequent "visit" (i.e. next QB which
                #      will come up in the next iteration)
                #   2. if all the submissions for the currentRP are
                #      non-deterministic*, we transition now and update the
                #      QNRs so they point to the QB of the nextRP
                #
                # * over RPs {v2,v3}, "epic23" vs "epic26" deterministically
                #   define the QB whereas "eortc" is non-deterministic, as
                #   it belongs to both

                transition_now = False
                cur_only, common, next_only = left_center_right(
                    current_qbd.questionnaire_instruments,
                    next_qbd.questionnaire_instruments)
                combined_instruments = cur_only.union(common).union(next_only)
                qnrs_for_period = user_qnrs.authored_during_period(
                    start=users_start, end=users_expiration,
                    restrict_to_instruments=combined_instruments)
                if len(qnrs_for_period) == 0:
                    transition_now = True

                period_instruments = set(
                    [q.instrument for q in qnrs_for_period])
                if not transition_now and period_instruments & cur_only:
                    if period_instruments & next_only:
                        current_app.logger.error(
                            "Transition ERROR, {} has deterministic QNRs "
                            "for multiple RPs '{}':'{}' during same visit; "
                            "User submitted {}; cur_only {}, common {}, "
                            "next_only {}".format(
                                user, curRPD.rp.name, nextRPD.rp.name,
                                str(period_instruments), str(cur_only),
                                str(common), str(next_only)))
                    # Don't transition yet, as definitive work on the old
                    # (current) RP has already been posted
                    transition_now = False
                else:
                    # Safe to transition, but first update all the common,
                    # existing QNRs to reference the *next* RP
                    for q in qnrs_for_period:
                        if q.instrument not in common:
                            continue
                        qnr = QuestionnaireResponse.query.get(q.qnr_id)
                        qnr.qb_id = next_qbd.qb_id
                        qnr.qb_iteration = next_qbd.iteration
                    transition_now = True

                if transition_now:
                    if (users_start, users_expiration) != (
                            next_start, next_expiration):
                        raise ValueError(
                            "Invalid state {}:{} not in lock-step; RPs need "
                            "to maintain same schedule".format(
                                curRPD.rp.name, nextRPD.rp.name))

                    curRPD, nextRPD = next(rp_walker)

                    # Need to "catch-up" the fresh generators to match current
                    # if we skipped ahead, only catch-up to the skipped_start
                    start = users_start
                    if skipped_next_start:
                        assert skipped_next_start < start
                        start = skipped_next_start
                    while True:
                        # Fear not, won't loop forever as `nextQBD` will
                        # quickly exhaust, thus raising an exception, in
                        # the event of a config error where RPs somehow
                        # change the start, expiration synchronization.
                        current_qbd, users_start, users_expiration = nextQBD(
                            curRPD.qbds)
                        if nextRPD:
                            next_qbd, next_start, next_expiration = nextQBD(
                                nextRPD.qbds)
                        if start == users_start:
                            break

                    # reset in case of another advancement
                    skipped_next_start = None

            # done if user withdrew before QB starts
            if withdrawal_date and withdrawal_date < users_start:
                trace("withdrawn as of {}".format(withdrawal_date))
                break

            current_qbd.relative_start = users_start
            # sanity check - make sure we don't adjust twice
            if hasattr(current_qbd, 'already_adjusted'):
                raise RuntimeError(
                    'already adjusted the qbd relative start')
            current_qbd.already_adjusted = True
            yield current_qbd

            current_qbd, users_start, users_expiration = nextQBD(
                curRPD.qbds)
            if nextRPD:
                next_qbd, next_start, next_expiration = nextQBD(nextRPD.qbds)
                if users_start != next_start:
                    # Valid when the RP being replaced doesn't have all the
                    # visits defined in the next one (i.e. v3 doesn't have
                    # months 27 or 33 and v5 does).  Look ahead for a match
                    skipped_next_start = next_start
                    next_qbd, next_start, next_expiration = nextQBD(
                        nextRPD.qbds)
                    if users_start != next_start:
                        # Still no match means poorly defined RP QBs
                        raise ValueError(
                            "Invalid state {}:{} not in lock-step even on "
                            "look ahead; RPs need to maintain same "
                            "schedule {}, {}, {}".format(
                                curRPD.rp.name, nextRPD.rp.name,
                                users_start, next_start, skipped_next_start))
            if not current_qbd:
                return
    else:
        trace("no RPs found")

        # No applicable RPs, try intervention associated QBs
        if classification == 'indefinite':
            iqbds = indef_intervention_qbs(user, trigger_date=td)
        else:
            iqbds = ordered_intervention_qbs(user, trigger_date=td)

        while True:
            try:
                qbd = next(iqbds)
            except StopIteration:
                return
            users_start = calc_and_adjust_start(
                user=user, qbd=qbd, initial_trigger=td)

            qbd.relative_start = users_start
            # sanity check - make sure we don't adjust twice
            if hasattr(qbd, 'already_adjusted'):
                raise RuntimeError('already adjusted the qbd relative start')
            qbd.already_adjusted = True
            yield qbd


def invalidate_users_QBT(user_id):
    """Mark the given user's QBT rows invalid (by deletion)"""
    QBT.query.filter(QBT.user_id == user_id).delete()
    db.session.commit()


def update_users_QBT(user_id, invalidate_existing=False):
    """Populate the QBT rows for given user

    :param user: the user to add QBT rows for
    :param invalidate_existing: set true to wipe any current rows first

    """
    def attempt_update(user_id, invalidate_existing):
        """Updates user's QBT or raises if lock is unattainable"""

        # acquire a multiprocessing lock to prevent multiple requests
        # from duplicating rows during this slow process
        timeout = int(current_app.config.get("MULTIPROCESS_LOCK_TIMEOUT"))
        key = "update_users_QBT user:{}".format(user_id)

        with TimeoutLock(key=key, timeout=timeout):
            if invalidate_existing:
                QBT.query.filter(QBT.user_id == user_id).delete()

            # if any rows are found, assume this user is current
            if QBT.query.filter(QBT.user_id == user_id).count():
                trace(
                    "found QBT rows, returning cached for {}".format(user_id))
                return

            user = User.query.get(user_id)
            if not user.has_role(ROLE.PATIENT.value):
                # Make it easier to find bogus use, by reporting user
                # and their roles in exception
                raise ValueError(
                    "{} with roles {} doesn't have timeline, only "
                    "patients".format(
                        user, str([r.name for r in user.roles])))

            # Create time line for user, from initial trigger date
            qb_generator = ordered_qbs(user)
            user_qnrs = QNR_results(user)

            # Force recalculation of QNR->QB association if needed
            if user_qnrs.qnrs_missing_qb_association():
                user_qnrs.assign_qb_relationships(qb_generator=ordered_qbs)

            # As we move forward, capture state at each time point

            pending_qbts = AtOrderedList()
            kwargs = {"user_id": user_id}
            for qbd in qb_generator:
                qb_recur_id = qbd.recur.id if qbd.recur else None
                kwargs = {
                    "user_id": user.id, "qb_id": qbd.questionnaire_bank.id,
                    "qb_iteration": qbd.iteration, "qb_recur_id": qb_recur_id}
                start = qbd.relative_start
                # Always add start (due)
                pending_qbts.append(QBT(at=start, status='due', **kwargs))

                expired_date = start + RelativeDelta(
                    qbd.questionnaire_bank.expired)
                overdue_date = None
                if qbd.questionnaire_bank.overdue:  # not all qbs define
                    overdue_date = start + RelativeDelta(
                        qbd.questionnaire_bank.overdue)
                partial_date = user_qnrs.earliest_result(
                    qbd.questionnaire_bank.id, qbd.iteration)
                include_overdue, include_expired = True, True
                complete_date, expired_as_partial = None, False

                # If we have at least one result for this (QB, iteration):
                if partial_date:
                    complete_date = user_qnrs.completed_date(
                        qbd.questionnaire_bank.id, qbd.iteration)

                    if partial_date != complete_date:
                        if overdue_date and partial_date < overdue_date:
                            include_overdue = False
                        if partial_date < expired_date:
                            pending_qbts.append(QBT(
                                at=partial_date, status='in_progress',
                                **kwargs))
                            # Without subsequent results, expired == partial
                            include_expired = False
                            expired_as_partial = True
                        else:
                            pending_qbts.append(QBT(
                                at=partial_date, status='partially_completed',
                                **kwargs))

                    if complete_date:
                        pending_qbts.append(QBT(
                            at=complete_date, status='completed',
                            **kwargs))
                        if complete_date <= expired_date:
                            include_overdue = False
                            include_expired = False
                            expired_as_partial = False

                if include_overdue and overdue_date:
                    # Take care to add overdue in the right order wrt
                    # partial and complete rows.

                    pending_qbts.append(QBT(
                        at=overdue_date, status='overdue', **kwargs))

                if expired_as_partial:
                    pending_qbts.append(QBT(
                        at=expired_date, status="partially_completed",
                        **kwargs))
                    if include_expired:
                        raise RuntimeError("conflicting state")

                if include_expired:
                    pending_qbts.append(QBT(
                        at=expired_date, status='expired', **kwargs))

            # If user withdrew from study - remove any rows post withdrawal
            num_stored = 0
            _, withdrawal_date = consent_withdrawal_dates(user)
            if withdrawal_date:
                trace("withdrawn as of {}".format(withdrawal_date))
                store_rows = [
                    qbt for qbt in pending_qbts if qbt.at < withdrawal_date]
                store_rows.append(
                    QBT(at=withdrawal_date, status='withdrawn', **kwargs))
                db.session.add_all(store_rows)
                num_stored = len(store_rows)
            else:
                db.session.add_all(pending_qbts)
                num_stored = len(pending_qbts)

            if num_stored:
                auditable_event(
                    message="qb_timeline updated; {} rows".format(num_stored),
                    user_id=user_id, subject_id=user_id, context="assessment")
            db.session.commit()

    success = False
    for attempt in range(1, 6):
        try:
            attempt_update(
                user_id=user_id, invalidate_existing=invalidate_existing)
            success = True
            break
        except ConnectionError as ce:
            current_app.logger.warning(
                "Failed to obtain lock for QBT on {} try; {}".format(
                    attempt, ce))
            sleep(1)  # give system a second to catch up
    if not success:
        current_app.logger.error(
            "couldn't obtain lock, recommend manual refresh of stale "
            "qb_timeline for {}".format(user_id))


class QB_StatusCacheKey(object):
    redis = None
    region_name = 'assessment_cache_region'
    key = "{}_as_of_date".format(__name__)

    def __init__(self):
        """init

        Establish redis connection and lookup configured max duration for key

        """
        # Lookup the configured expiration of the matching cache
        # container ("DOGPILE_CACHE_REGIONS" -> "assessment_cache_region")
        if self.redis is None:
            self.redis = redis.StrictRedis.from_url(
                current_app.config['REDIS_URL'])
        regions = current_app.config['DOGPILE_CACHE_REGIONS']
        for region_name, duration in regions:
            if region_name == self.region_name:
                self.valid_duration = relativedelta(seconds=duration)
        if not self.valid_duration:
            raise RuntimeError("unable to locate configured cache timeout")

    def minutes_old(self):
        """Return human friendly string for age of cache key

        Looks up the age of self.key WRT utcnow, and return the approximate
        minute value.

        :returns: approximate number of minutes since renewal of cache key

        """
        now = datetime.utcnow()
        delta = relativedelta(now, self.current())
        return delta.hours * 60 + delta.minutes

    def current(self):
        """Returns current as_of_date value

        If a valid datetime value is found to be within the max configured
        duration, return it.  Otherwise, store utcnow (for subsequent use)
        and return that.

        :returns: a valid (UTC) datetime, either the current cached value or
          a new, if the old has expired or was not found.

        """
        now = datetime.utcnow()
        value = self.redis.get(self.key)
        if value:
            try:
                value = FHIR_datetime.parse(value)
                if value + self.valid_duration > now:
                    return value
            except BadRequest:
                if value is not None:
                    current_app.logger.warning(
                        "Can't parse as datetime {}".format(value))
        return self.update(now)

    def update(self, value):
        """Updates the cache key to given value"""
        if not isinstance(value, datetime):
            raise ValueError('expected datetime for key value')
        now = datetime.utcnow()
        if value + self.valid_duration < now:
            raise ValueError('expect valid datetime - {} too old'.format(
                value))
        if value > now + relativedelta(seconds=5):
            raise ValueError('future dates not acceptable keys')

        stringform = FHIR_datetime.as_fhir(value)
        self.redis.set(self.key, stringform)
        return stringform


@dogpile_cache.region('assessment_cache_region')
def qb_status_visit_name(user_id, as_of_date):
    """Return (status, visit name) for current QB for user as of given date

    If no data is available for the user, returns (expired, None)

    """

    # should be cached, unless recently invalidated
    update_users_QBT(user_id)

    # We order by at (to get the latest status for a given QB) and
    # secondly by id, as on rare occasions, the time (`at`) of
    #  `due` == `completed`, but the row insertion defines priority
    qbt = QBT.query.filter(QBT.user_id == user_id).filter(
        QBT.at <= as_of_date).order_by(
        QBT.at.desc(), QBT.id.desc()).first()
    if qbt:
        return qbt.status, visit_name(qbt.qbd())
    return OverallStatus.expired, None


def expires(user_id, qbd):
    """Accessor to lookup 'expires' date for given user/qbd

    :returns: the expires date for the given user/QBD; None if not found.

    """
    # should be cached, unless recently invalidated
    update_users_QBT(user_id)

    # We order by at (to get the latest status for a given QB) and
    # secondly by id, as on rare occasions, the time (`at`) of
    #  `due` == `completed`, but the row insertion defines priority
    qbt = QBT.query.filter(QBT.user_id == user_id).filter(
        QBT.qb_id == qbd.qb_id).filter(
        QBT.qb_iteration == qbd.iteration).order_by(
        QBT.at.desc(), QBT.id.desc()).first()
    if qbt and qbt.status in (
            OverallStatus.completed, OverallStatus.partially_completed,
            OverallStatus.expired):
        return qbt.at
