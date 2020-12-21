from collections import namedtuple
from datetime import MAXYEAR, datetime
from time import sleep

from dateutil.relativedelta import relativedelta
from flask import current_app
import redis
from redis.exceptions import ConnectionError
from sqlalchemy.types import Enum as SQLA_Enum
from werkzeug.exceptions import BadRequest

from ..audit import Audit, auditable_event
from ..cache import cache, TWO_HOURS
from ..database import db
from ..date_tools import FHIR_datetime, RelativeDelta
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

    """
    __tablename__ = 'qb_timeline'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey(
        'users.id', ondelete='cascade'), nullable=False, index=True)
    at = db.Column(
        db.DateTime, nullable=False, index=True,
        doc="initial date time for state of row")
    qb_id = db.Column(db.ForeignKey(
        'questionnaire_banks.id', ondelete='cascade'), nullable=True)
    qb_recur_id = db.Column(db.ForeignKey(
        'recurs.id', ondelete='cascade'), nullable=True)
    qb_iteration = db.Column(db.Integer, nullable=True)
    status = db.Column(SQLA_Enum(OverallStatus), nullable=False, index=True)
    research_study_id = db.Column(db.ForeignKey(
        'research_studies.id', ondelete='cascade'),
        nullable=False, index=True)

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


def calc_and_adjust_start(user, research_study_id, qbd, initial_trigger):
    """Calculate correct start for user on given QBD

    A QBD is initially generated with a generic trigger date for
    caching and sorting needs.  This function translates the
    given QBD.relative_start to the users situation.

    :param user: subject user
    :param research_study_id: research study being processed
    :param qbd: QBD with respect to system trigger
    :param initial_trigger: datetime value used in initial QBD calculation

    :returns adjusted `relative_start` for user

    """
    users_trigger = trigger_date(
        user, research_study_id=research_study_id, qb=qbd.questionnaire_bank)
    if not users_trigger:
        trace(
            "no valid trigger, default to initial value: {}".format(
                initial_trigger))
        users_trigger = initial_trigger
    if initial_trigger > users_trigger:
        trace(
            "user {} has unexpected trigger date before consent date".format(
                user.id))

    if not qbd.relative_start:
        raise RuntimeError("can't adjust without relative_start")

    if users_trigger == initial_trigger:
        return qbd.relative_start

    delta = users_trigger - initial_trigger
    current_app.logger.debug("calc_and_adjust_start delta: %s", str(delta))
    return qbd.relative_start + delta


def calc_and_adjust_expired(user, research_study_id, qbd, initial_trigger):
    """Calculate correct expired for user on given QBD

    A QBD is initially generated with a generic trigger date for
    caching and sorting needs.  This function translates the
    given QBD.relative_start to the users situation.

    :param user: subject user
    :param research_study_id: research study being processed
    :param qbd: QBD with respect to system trigger
    :param initial_trigger: datetime value used in initial QBD calculation

    :returns adjusted `relative_start` for user

    """
    users_trigger = trigger_date(
        user, research_study_id=research_study_id, qb=qbd.questionnaire_bank)
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
    if not qbd.relative_start:
        raise RuntimeError("can't adjust without relative_start")

    if users_trigger != initial_trigger:
        delta = users_trigger - initial_trigger + RelativeDelta(expired)
        current_app.logger.debug(
            "calc_and_adjust_expired delta: %s", str(delta))
    else:
        delta = RelativeDelta(expired)
    return qbd.relative_start + delta


max_sort_time = datetime(year=MAXYEAR, month=12, day=31)


def second_null_safe_datetime(x):
    """datetime sort accessor treats None as far off in the future"""
    if not x[1]:
        return max_sort_time
    return x[1]


RPD = namedtuple("RPD", ['rp', 'retired', 'qbds'])


def cur_next_rp_gen(user, research_study_id, classification, trigger_date):
    """Generator to manage transitions through research protocols

    Returns a *pair* of research protocol data (RPD) namedtuples,
    one for current (active) RP data, one for the "next".

    :param user: applicable patient
    :param research_study_id: study being processed
    :param classification: None or 'indefinite' for special handling
    :param trigger_date: patient's initial trigger date

    :yields: cur_RPD, next_RPD

    """
    rps = ResearchProtocol.assigned_to(user, research_study_id)
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
        trace("current RP '{}'({}), next RP '{}'({})".format(
            current_rp.name, current_rp.id, next_rp.name
            if next_rp else 'None', next_rp.id if next_rp else 'None'))

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


class RP_flyweight(object):
    """maintains state for RPs as it transitions

    Any number of Research Protocols may apply to a user.  This
    class manages transitioning through the applicable as time
    passes, maintaining a "current" and "next" as well as the ability
    to continue marching forward.

    """

    def __init__(self, user, trigger_date, research_study_id, classification):
        """Initialize flyweight state
        :param user: the patient
        :param trigger_date: the patient's initial trigger date
        :param research_study_id: the study being processed
        :param classification: `indefinite` or None
        """
        self.user = user
        self.td = trigger_date
        self.research_study_id = research_study_id
        self.classification = classification
        self.rp_walker = cur_next_rp_gen(
            user=self.user,
            research_study_id=self.research_study_id,
            trigger_date=self.td,
            classification=self.classification)
        self.cur_rpd, self.nxt_rpd = next(self.rp_walker, (None, None))
        self.skipped_nxt_start = None

    def adjust_start(self):
        """The QB start may need a minor adjustment, done once when ready"""
        self.cur_qbd.relative_start = self.cur_start

        # sanity check - make sure we don't adjust twice
        if hasattr(self.cur_qbd, 'already_adjusted'):
            raise RuntimeError(
                'already adjusted the qbd relative start')
        self.cur_qbd.already_adjusted = True

    def consider_transition(self):
        """Returns true only if state suggests it *may* be transtion time"""
        return self.nxt_rpd and self.cur_rpd.retired < self.cur_exp

    def next_qbd(self):
        """Advance to next qbd on applicable RPs"""
        self.cur_qbd, self.cur_start, self.cur_exp = None, None, None
        if self.cur_rpd:
            self.cur_qbd = next(self.cur_rpd.qbds, None)
        if self.cur_qbd:
            self.cur_start = calc_and_adjust_start(
                user=self.user,
                research_study_id=self.research_study_id,
                qbd=self.cur_qbd,
                initial_trigger=self.td)
            self.cur_exp = calc_and_adjust_expired(
                user=self.user,
                research_study_id=self.research_study_id,
                qbd=self.cur_qbd,
                initial_trigger=self.td)

        self.nxt_qbd, self.nxt_start = None, None
        if self.nxt_rpd:
            self.nxt_qbd = next(self.nxt_rpd.qbds, None)
        if self.nxt_qbd:
            self.nxt_start = calc_and_adjust_start(
                user=self.user,
                research_study_id=self.research_study_id,
                qbd=self.nxt_qbd,
                initial_trigger=self.td)
            self.nxt_exp = calc_and_adjust_expired(
                user=self.user,
                research_study_id=self.research_study_id,
                qbd=self.nxt_qbd,
                initial_trigger=self.td)
            if self.cur_qbd is None:
                trace("Finished cur RP with remaining QBs in next")
                self.cur_start = self.nxt_start
                self.transition()
            elif self.cur_start > self.nxt_start + relativedelta(months=1):
                # The plus one month covers RP v5 date adjustments.

                # Valid only when the RP being replaced doesn't have all the
                # visits defined in the next one (i.e. v3 doesn't have months
                # 27 or 33 and v5 does). Look ahead for a match
                self.skipped_nxt_start = self.nxt_start
                self.nxt_start = None
                self.nxt_qbd = next(self.nxt_rpd.qbds, None)
                if self.nxt_qbd:
                    self.nxt_start = calc_and_adjust_start(
                        user=self.user,
                        research_study_id=self.research_study_id,
                        qbd=self.nxt_qbd,
                        initial_trigger=self.td)
                    self.nxt_exp = calc_and_adjust_expired(
                        user=self.user, qbd=self.nxt_qbd,
                        initial_trigger=self.td)
                if self.cur_start > self.nxt_start + relativedelta(months=1):
                    # Still no match means poorly defined RP QBs
                    raise ValueError(
                        "Invalid state {}:{} not in lock-step even on "
                        "look ahead; RPs need to maintain same "
                        "schedule {}, {}, {}".format(
                            self.cur_rpd.rp.name, self.nxt_rpd.rp.name,
                            self.cur_start, self.nxt_start,
                            self.skipped_nxt_start))
        if self.cur_qbd:
            trace("advanced to next QB: {}({}) [{} - {})".format(
                self.cur_qbd.questionnaire_bank.name,
                self.cur_qbd.iteration,
                self.cur_start,
                self.cur_exp))
        else:
            trace("out of QBs!")

    def transition(self):
        """Transition internal state to 'next' Research Protocol"""
        trace("transitioning to the next RP [{} - {})".format(
            self.cur_start, self.cur_exp))
        if self.cur_start > self.nxt_start + relativedelta(months=1):
            # The plus one month covers RP v5 shift
            raise ValueError(
                "Invalid state {}:{} not in lock-step; RPs need "
                "to maintain same schedule".format(
                    self.cur_rpd.rp.name, self.nxt_rpd.rp.name))

        self.cur_rpd, self.nxt_rpd = next(self.rp_walker)

        # Need to "catch-up" the fresh generators to match current
        # if we skipped ahead, only catch-up to the skipped_start
        start = self.cur_start
        if self.skipped_nxt_start:
            assert self.skipped_nxt_start < start
            start = self.skipped_nxt_start
        entropy_check = 99
        while True:
            entropy_check -= 1
            if entropy_check < 0:
                raise RuntimeError("entropy wins again; QB configs out of sync")

            self.next_qbd()
            if start < self.cur_start + relativedelta(months=1):
                # due to early start for RP v5, add a month before comparison
                break

        # reset in case of another advancement
        self.skipped_nxt_start = None

        # confirm the now current isn't already retired. rare situation that
        # happens when an org has retired multiple RPs before a user's trigger
        if (
                self.cur_rpd.retired and
                self.cur_rpd.retired < self.td and
                self.consider_transition()):
            trace('fire double transition as RP retired before user trigger')
            self.transition()


def ordered_qbs(user, research_study_id, classification=None):
    """Generator to yield ordered qbs for a user, research_study

    This does NOT include the indefinite classification unless requested,
     as it plays by a different set of rules.

    :param user: the user to lookup
    :param research_study_id: the research study being processed
    :param classification: set to ``indefinite`` for that special handling
    :returns: QBD for each (QB, iteration, recur)

    """
    if classification == 'indefinite':
        trace("begin ordered_qbds() on `indefinite` classification")
    elif classification is not None:
        raise ValueError(
            "only 'indefinite' or default (None) classifications allowed")

    # bootstrap problem - don't know initial `as_of_date` w/o a QB
    # call `trigger_date` w/o QB for best guess.
    td = trigger_date(user=user, research_study_id=research_study_id)
    old_td, withdrawal_date = consent_withdrawal_dates(
        user, research_study_id=research_study_id)
    if not td:
        if old_td and withdrawal_date:
            trace("withdrawn user, use previous trigger {}".format(old_td))
            td = old_td
        else:
            trace("no trigger date therefore nothing from ordered_qbds()")
            return
    else:
        trace("initial trigger date {}".format(td))

    rp_flyweight = RP_flyweight(
        user=user,
        trigger_date=td,
        research_study_id=research_study_id,
        classification=classification)

    if rp_flyweight.cur_rpd:
        user_qnrs = QNR_results(user, research_study_id=research_study_id)
        rp_flyweight.next_qbd()

        if not rp_flyweight.cur_qbd:
            trace("no current found in initial QBD lookup, bail")
            return

        while True:
            if rp_flyweight.consider_transition():
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
                    rp_flyweight.cur_qbd.questionnaire_instruments,
                    rp_flyweight.nxt_qbd.questionnaire_instruments)
                combined_instruments = cur_only.union(common).union(next_only)
                qnrs_for_period = user_qnrs.authored_during_period(
                    start=rp_flyweight.cur_start, end=rp_flyweight.cur_exp,
                    restrict_to_instruments=combined_instruments)

                # quick check if current is done, as overlapping QBs pull
                # in QNRs from upcoming QBs
                unfinished = rp_flyweight.cur_qbd.questionnaire_instruments
                for qnr in qnrs_for_period:
                    if (
                            qnr.status == 'completed' and
                            qnr.instrument in unfinished):
                        unfinished.remove(qnr.instrument)

                if len(qnrs_for_period) == 0:
                    transition_now = True

                # Indefinite requires special handling
                if classification == 'indefinite' and not unfinished:
                    yield rp_flyweight.cur_qbd
                    return

                period_instruments = set(
                    [q.instrument for q in qnrs_for_period])
                if not transition_now and period_instruments & cur_only:
                    # Posted results tie user to the old RP; clear skipped
                    # state as it's unavailable when results from the "next"
                    # exist, unless it's all done.
                    if unfinished:
                        rp_flyweight.skipped_nxt_start = None

                    # Don't transition yet, as definitive work on the old
                    # (current) RP has already been posted, UNLESS ...
                    if period_instruments & next_only and unfinished:
                        current_app.logger.warning(
                            "Transition surprise, {} has deterministic QNRs "
                            "for multiple RPs '{}':'{}' during same visit; "
                            "User submitted {}; cur_only {}, common {}, "
                            "next_only {}.  Moving to newer RP".format(
                                user, rp_flyweight.cur_rpd.rp.name,
                                rp_flyweight.nxt_rpd.rp.name,
                                str(period_instruments), str(cur_only),
                                str(common), str(next_only)))
                        trace("deterministic for both RPs! transition")
                        transition_now = True
                else:
                    transition_now = True

                if transition_now:
                    rp_flyweight.transition()

            # done if user withdrew before QB starts
            if withdrawal_date and withdrawal_date < rp_flyweight.cur_start:
                trace("withdrawn as of {}".format(withdrawal_date))
                break

            rp_flyweight.adjust_start()
            yield rp_flyweight.cur_qbd

            rp_flyweight.next_qbd()
            if not rp_flyweight.cur_qbd:
                return
    else:
        trace("no RPs found")

        # No applicable RPs, try intervention associated QBs
        if classification == 'indefinite':
            iqbds = indef_intervention_qbs(
                user, trigger_date=td)
        else:
            iqbds = ordered_intervention_qbs(
                user, trigger_date=td)

        while True:
            try:
                qbd = next(iqbds)
            except StopIteration:
                return
            users_start = calc_and_adjust_start(
                user=user,
                research_study_id=research_study_id,
                qbd=qbd,
                initial_trigger=td)

            qbd.relative_start = users_start
            # sanity check - make sure we don't adjust twice
            if hasattr(qbd, 'already_adjusted'):
                raise RuntimeError('already adjusted the qbd relative start')
            qbd.already_adjusted = True
            yield qbd


def invalidate_users_QBT(user_id, research_study_id):
    """Mark the given user's QBT rows invalid (by deletion)

    :param user_id: user for whom to purge all QBT rows
    :param research_study_id: set to limit invalidation to research study or
      use string 'all' to invalidate all QBT rows for a user

    """
    if research_study_id == 'all':
        QBT.query.filter(QBT.user_id == user_id).delete()
    else:
        QBT.query.filter(QBT.user_id == user_id).filter(
            QBT.research_study_id == research_study_id).delete()

    # args have to match order and values - no wild carding avail
    as_of = QB_StatusCacheKey().current()
    if research_study_id != 'all':
        cache.delete_memoized(
            qb_status_visit_name, user_id, research_study_id, as_of)
    else:
        # quicker to just clear both than look up what user belongs to
        cache.delete_memoized(
            qb_status_visit_name, user_id, 0, as_of)
        cache.delete_memoized(
            qb_status_visit_name, user_id, 1, as_of)

    db.session.commit()


def update_users_QBT(user_id, research_study_id, invalidate_existing=False):
    """Populate the QBT rows for given user, research_study

    :param user: the user to add QBT rows for
    :param research_study_id: the research study being processed
    :param invalidate_existing: set true to wipe any current rows first

    A user may be eligible for any number of research studies.  QBT treats
    each (user, research_study) independently, as should clients.

    """
    def attempt_update(user_id, research_study_id, invalidate_existing):
        """Updates user's QBT or raises if lock is unattainable"""
        from .qb_status import patient_research_study_status

        # acquire a multiprocessing lock to prevent multiple requests
        # from duplicating rows during this slow process
        timeout = int(current_app.config.get("MULTIPROCESS_LOCK_TIMEOUT"))
        key = "update_users_QBT user:study {}:{}".format(
            user_id, research_study_id)

        with TimeoutLock(key=key, timeout=timeout):
            if invalidate_existing:
                QBT.query.filter(QBT.user_id == user_id).filter(
                    QBT.research_study_id == research_study_id).delete()

            # if any rows are found, assume this user/study is current
            if QBT.query.filter(QBT.user_id == user_id).filter(
                    QBT.research_study_id == research_study_id).count():
                trace(
                    "found QBT rows, returning cached for {}:{}".format(
                        user_id, research_study_id))
                return

            user = User.query.get(user_id)
            if not user.has_role(ROLE.PATIENT.value):
                # Make it easier to find bogus use, by reporting user
                # and their roles in exception
                raise ValueError(
                    "{} with roles {} doesn't have timeline, only "
                    "patients".format(
                        user, str([r.name for r in user.roles])))

            # Check eligibility - some studies aren't available till
            # business rules have been met
            study_eligibility = [
                study for study in patient_research_study_status(
                    user, ignore_QB_status=True) if
                study['research_study_id'] == research_study_id]

            if not study_eligibility or not study_eligibility[0]['eligible']:
                trace(f"user determined ineligible for {research_study_id}")
                return

            # Create time line for user, from initial trigger date
            qb_generator = ordered_qbs(user, research_study_id)
            user_qnrs = QNR_results(user, research_study_id)

            # Force recalculation of QNR->QB association if needed
            if user_qnrs.qnrs_missing_qb_association():
                user_qnrs.assign_qb_relationships(qb_generator=ordered_qbs)

            # As we move forward, capture state at each time point

            pending_qbts = AtOrderedList()
            for qbd in qb_generator:
                qb_recur_id = qbd.recur.id if qbd.recur else None
                kwargs = {
                    "user_id": user.id,
                    "research_study_id": research_study_id,
                    "qb_id": qbd.questionnaire_bank.id,
                    "qb_iteration": qbd.iteration,
                    "qb_recur_id": qb_recur_id}
                start = qbd.relative_start

                if (
                        pending_qbts and pending_qbts[-1].at > start and
                        pending_qbts[-1].status != 'expired'):
                    # This large & unfortunate HACK is necessary w/
                    # overlapping QBs due to protocol change as there's
                    # inadequate state available w/i the generator.

                    # Unique edge case that only happens when user filled
                    # out results from the previous QB that belongs to the
                    # previous RP, AND the new RP inserted a skipped visit
                    # AND now we find the skipped visit starts BEFORE the
                    # results were committed to the previous QB.  In such a
                    # case we need to ignore the skipped and move on.
                    trace(
                        "Found overlapping dates and results on former;"
                        f" NOT adding {qbd}")

                    # For questionnaires with common instrument names that
                    # happen to fit in both QBs, need to now reassign the
                    # QB associations as the second is getting tossed
                    changed = user_qnrs.reassign_qb_association(
                        existing={
                            'qb_id': qbd.qb_id,
                            'iteration': qbd.iteration},
                        desired={
                            'qb_id': pending_qbts[-1].qb_id,
                            'iteration': pending_qbts[-1].qb_iteration})

                    # IF the reassignment caused a change, AND the previous
                    # visit was in a partially_completed state AND the change
                    # now completes that visit, update the status.
                    if (
                            changed and
                            pending_qbts[-1].status == 'partially_completed'):
                        complete_date = user_qnrs.completed_date(
                            pending_qbts[-1].qb_id,
                            pending_qbts[-1].qb_iteration)
                        if complete_date:
                            pending_qbts[-1].at = complete_date
                            pending_qbts[-1].status = 'completed'

                    continue  # effectively removes the unwanted visit

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
            _, withdrawal_date = consent_withdrawal_dates(
                user, research_study_id=research_study_id)
            if withdrawal_date:
                trace("withdrawn as of {}".format(withdrawal_date))
                store_rows = [
                    qbt for qbt in pending_qbts if qbt.at < withdrawal_date]
                store_rows.append(QBT(
                    at=withdrawal_date,
                    status='withdrawn',
                    user_id=user_id,
                    research_study_id=research_study_id))
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
                user_id=user_id,
                research_study_id=research_study_id,
                invalidate_existing=invalidate_existing)
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
    """Maintains the recent enough ``as_of_date`` parameter

    In order to leverage a cached value from ``qb_status_visit_name``,
    the ``as_of_date`` parameter can't be constantly rolling forward
    with the progress of ``now()``.

    This class maintains a recent enough value for as_of_date, with
    methods to reset and inform user how stale it is.

    """
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
        """Returns current as_of_date value, as in recent enough for caching

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
        return value


@cache.memoize(timeout=TWO_HOURS)
def qb_status_visit_name(user_id, research_study_id, as_of_date):
    """Return details for current QB for user as of given date

    NB to take advantage of caching, clients should use
    ``QB_StatusCacheKey.current()`` for as_of_date parameter, to avoid
    a new lookup with each passing moment.

    If no data is available for the user, returns
     {'status': 'expired', 'visit_name': None}

    :returns: dictionary with key/values for:
      status: string like 'expired'
      visit_name: for the period, i.e. '3 months'
      action_state: 'not applicable', or status of follow up action

    """
    from .research_study import EMPRO_RS_ID

    assert isinstance(research_study_id, int)
    assert isinstance(as_of_date, datetime)

    results = {
        'status': OverallStatus.expired,
        'visit_name': None,
        'action_state': 'not applicable'
    }

    # should be cached, unless recently invalidated - confirm
    update_users_QBT(user_id, research_study_id=research_study_id)

    # We order by at (to get the latest status for a given QB) and
    # secondly by id, as on rare occasions, the time (`at`) of
    #  `due` == `completed`, but the row insertion defines priority
    qbt = QBT.query.filter(QBT.user_id == user_id).filter(
        QBT.research_study_id == research_study_id).filter(
        QBT.at <= as_of_date).order_by(
        QBT.at.desc(), QBT.id.desc()).first()
    if qbt:
        results['status'] = qbt.status
        results['visit_name'] = visit_name(qbt.qbd())

        if research_study_id == EMPRO_RS_ID:
            # Not available to all products, thus the nested import
            from ..trigger_states.models import TriggerState

            # month count present only beyond baseline
            if qbt.qbd().questionnaire_bank.classification == 'baseline':
                visit_month = 0
            else:
                # pull digit from possibly translated string
                digits = [
                    int(s) for s in results['visit_name'].split()
                    if s.isdigit()]
                assert len(digits) == 1
                visit_month = digits[0]

            ts = TriggerState.query.filter(
                TriggerState.user_id == user_id).filter(
                TriggerState.visit_month == visit_month).order_by(
                TriggerState.timestamp.desc()).first()
            if ts and ts.triggers:
                results['action_state'] = ts.triggers.get(
                    'action_state', 'due')
            else:
                results['action_state'] = 'due'

    return results


def expires(user_id, qbd):
    """Accessor to lookup 'expires' date for given user/qbd

    :returns: the expires date for the given user/QBD; None if not found.

    """
    research_study_id = qbd.questionnaire_bank.research_study_id

    # should be cached, unless recently invalidated
    update_users_QBT(user_id, research_study_id)

    # We order by at (to get the latest status for a given QB) and
    # secondly by id, as on rare occasions, the time (`at`) of
    #  `due` == `completed`, but the row insertion defines priority
    qbt = QBT.query.filter(QBT.user_id == user_id).filter(
        QBT.qb_id == qbd.qb_id).filter(
        QBT.research_study_id == research_study_id).filter(
        QBT.qb_iteration == qbd.iteration).order_by(
        QBT.at.desc(), QBT.id.desc()).first()
    if qbt and qbt.status in (
            OverallStatus.completed, OverallStatus.partially_completed,
            OverallStatus.expired):
        return qbt.at
