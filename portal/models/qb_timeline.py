from collections import namedtuple
from datetime import MAXYEAR, datetime
from time import sleep

from dateutil.relativedelta import relativedelta
from flask import current_app
from redis.exceptions import ConnectionError
from sqlalchemy.types import Enum as SQLA_Enum
from werkzeug.exceptions import BadRequest

from ..audit import auditable_event
from ..cache import cache, TWO_HOURS
from ..database import db
from ..date_tools import FHIR_datetime, RelativeDelta
from ..factories.redis import create_redis
from ..set_tools import left_center_right
from ..timeout_lock import ADHERENCE_DATA_KEY, CacheModeration, TimeoutLock
from ..trace import trace
from .adherence_data import AdherenceData
from .overall_status import OverallStatus
from .qbd import QBD
from .questionnaire_bank import (
    qbs_by_intervention,
    qbs_by_rp,
    trigger_date,
    visit_name,
)
from .questionnaire_response import QNR_results, QuestionnaireResponse
from .research_data import ResearchData
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

    def __repr__(self):
        """simplifies debugging"""
        return (
            f"{visit_name(self.qbd())}({self.qb_id}:{self.qb_iteration})"
            f" {self.status} @ {self.at}")

    @staticmethod
    def timeline_state(user_id):
        """Return an ordered list of user's QBT state for tracking changes"""
        from .questionnaire_bank import QuestionnaireBank
        name_map = QuestionnaireBank.name_map()
        tl = QBT.query.filter(
            QBT.user_id == user_id).with_entities(
            QBT.at,
            QBT.qb_id,
            QBT.status,
            QBT.qb_iteration).order_by(
            QBT.at)

        results = dict()
        for i in tl:
            qb = QuestionnaireBank.query.get(i.qb_id)
            if qb is None:
                continue
            recur_id = qb.recurs[0].id if qb.recurs else None
            vn = visit_name(QBD(
                relative_start=None,
                questionnaire_bank=qb,
                iteration=i.qb_iteration,
                recur_id=recur_id))
            results[f"{i.at} {i.status}"] = [
                vn, name_map[i.qb_id], i.qb_iteration]
        return results


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
    if len(baselines) > 1:
        raise RuntimeError(
            "Expect exactly one QB for baseline by rp {}".format(rp_id))
    if len(baselines) == 0:
        # typically only test scenarios - easy catch otherwise
        return
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
    # this case should no longer be possible; raise the alarm
    raise RuntimeError("found user(%d) initial trigger to differ by: %s", user.id, str(delta))
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
                    "Invalid state: multiple RPs w/ same retire date: "
                    f"{next_rp} : {curRPD.retired}")
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

    def __repr__(self):
        """strictly for enhanced debugging"""
        r = []
        r.append(
            f"current: {self.cur_rpd.rp.name}"
            f"(till: {self.cur_rpd.retired}) "
            f"cur_qb: [{self.cur_start}<->{self.cur_exp})")
        if self.nxt_qbd:
            r.append(
                f"next: {self.nxt_rpd.rp.name} "
                f"next_qb: [{self.nxt_start}<->{self.nxt_exp})")
        return '\n'.join(r)

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
                        research_study_id=self.research_study_id,
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

    def pre_loop_transition(self):
        """Check start state before looping through timeline

        If the organization has already retired one or more RPs,
        step forward to the correct starting RP

        """
        # confirm the now current isn't already retired. rare situation that
        # happens when an org has retired multiple RPs before a user's trigger

        # historically, Research Protocol changes recorded in persistence
        # files include retroactive dates, that is retired values far in the
        # past.  add a safe buffer as a "look ahead", so we don't move too
        # far in the RP history - allowing for the checks in `ordered_qbs()`
        # to tie a user to the older, well retired RP if they have submitted
        # QuestionnaireResponses defining the older RP.
        retro_buffer = relativedelta(months=9)
        while True:
            # indefinite plays by a different set of rules
            if self.classification == 'indefinite':
                if (
                        self.cur_rpd.retired and
                        self.cur_rpd.retired + retro_buffer < self.td and
                        self.consider_transition()):
                    trace('pre-loop transition as RP retired before user trigger')
                    self.transition()
                else:
                    break
            else:
                if self.consider_transition() and (
                        self.cur_rpd.retired + retro_buffer) < self.cur_start:
                    trace('pre-loop transition')
                    self.transition()
                else:
                    break

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


def ordered_qbs(user, research_study_id, classification=None):
    """Generator to yield ordered qbs for a user, research_study

    This does NOT include the indefinite classification unless requested,
     as it plays by a different set of rules.

    :param user: the user to look up
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

        rp_flyweight.pre_loop_transition()
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
    """invalidate the given user's QBT rows and related cached data, by deletion

    This also clears a users cached adherence and research data rows from their
    respective caches.

    :param user_id: user for whom to purge all QBT rows
    :param research_study_id: set to limit invalidation to research study or
      use string 'all' to invalidate all QBT rows for a user

    """
    if research_study_id is None:
        raise ValueError('research_study_id must be defined or use "all"')
    if research_study_id == 'all':
        QBT.query.filter(QBT.user_id == user_id).delete()
        AdherenceData.query.filter(
            AdherenceData.patient_id == user_id).delete()
        ResearchData.query.filter(ResearchData.subject_id == user_id).delete()
    else:
        QBT.query.filter(QBT.user_id == user_id).filter(
            QBT.research_study_id == research_study_id).delete()
        adh_data = AdherenceData.query.filter(
            AdherenceData.patient_id == user_id).filter(
            AdherenceData.rs_id_visit.like(f"{research_study_id}:%"))
        # SQL alchemy can't combine `like` expression with delete op.
        for ad in adh_data:
            db.session.delete(ad)
        ResearchData.query.filter(ResearchData.subject_id == user_id).filter(
            ResearchData.research_study_id == research_study_id).delete()

        if not current_app.config.get("TESTING", False):
            # clear the timeout lock as well, since we need a refresh
            # after deletion of the adherence data
            # otherwise, we experience a deadlock situation where tables can't be dropped 
            # between test runs, as postgres believes a deadlock condition exists
            cache_moderation = CacheModeration(key=ADHERENCE_DATA_KEY.format(
                patient_id=user_id,
                research_study_id=research_study_id))
            cache_moderation.reset()


    # clear cached qb_status_visit_name() using current as_of value
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


def check_for_overlaps(qbt_rows, cli_presentation=False):
    """Sanity function to confirm users timeline doesn't contain overlaps"""
    # Expect ordered rows with increasing `at` values.  Track (QB,iterations)
    # seen, notify if overlaps are discovered.
    from .questionnaire_bank import QuestionnaireBank

    def rp_name_from_qb_id(qb_id):
        return ResearchProtocol.query.join(QuestionnaireBank).filter(
            QuestionnaireBank.research_protocol_id ==
            ResearchProtocol.id).filter(
            QuestionnaireBank.id == qb_id).with_entities(
            ResearchProtocol.name).first()[0]

    def int_or_none(value):
        """None safe int cast from string"""
        if value is None or value == 'None':
            return None
        return int(value)

    seen = set()
    last_at, previous_key = None, None
    reported_on = set()
    for row in qbt_rows:
        # Confirm expected order
        if last_at:
            if last_at > row.at:
                raise ValueError(
                    f"patient {row.user_id} has overlapping qb_timeline rows"
                    f" {last_at} and {row.at}"
                )

        key = f"{row.qb_id}:{row.qb_iteration}"
        if previous_key and previous_key != key:
            # just moved to next visit, confirm it's novel
            if key in seen:
                overlap = row.at - last_at
                if overlap and not (key in reported_on and previous_key in reported_on):
                    qb_id, iteration = [
                        int_or_none(x) for x in previous_key.split(':')]
                    prev_visit = " ".join(
                        (visit_name(qbd=QBD(
                            relative_start=None,
                            iteration=iteration,
                            qb_id=qb_id,
                            recur_id=previous_recur_id)),
                         rp_name_from_qb_id(qb_id)))
                    visit = " ".join(
                        (visit_name(qbd=QBD(
                            relative_start=None,
                            iteration=row.qb_iteration,
                            qb_id=row.qb_id,
                            recur_id=row.qb_recur_id)),
                         rp_name_from_qb_id(row.qb_id)))

                    m = (
                        f"{visit}, {prev_visit} overlap by {overlap} for"
                        f" {row.user_id}")
                    if cli_presentation:
                        print(m)
                    else:
                        current_app.logger.error(m)

                # Don't report the back and forth, once is adequate.
                reported_on.add(key)
                reported_on.add(previous_key)

        previous_key = key
        previous_recur_id = row.qb_recur_id
        seen.add(key)
        last_at = row.at
    if reported_on:
        # Returns true if at least one overlap was found
        return True


def update_users_QBT(user_id, research_study_id):
    """Populate the QBT rows for given user, research_study

    :param user: the user to add QBT rows for
    :param research_study_id: the research study being processed

    A user may be eligible for any number of research studies.  QBT treats
    each (user, research_study) independently, as should clients.

    """
    def attempt_update(user_id, research_study_id):
        """Updates user's QBT or raises if lock is unattainable"""
        from .qb_status import patient_research_study_status
        from ..tasks import LOW_PRIORITY, cache_single_patient_adherence_data

        # acquire a multiprocessing lock to prevent multiple requests
        # from duplicating rows during this slow process
        timeout = int(current_app.config.get("MULTIPROCESS_LOCK_TIMEOUT"))
        key = "update_users_QBT user:study {}:{}".format(
            user_id, research_study_id)

        with TimeoutLock(key=key, timeout=timeout):
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
            rss = patient_research_study_status(user, ignore_QB_status=True)
            study_eligibility = (
                research_study_id in rss and rss[research_study_id]['eligible'])

            if not study_eligibility:
                trace(f"user determined ineligible for {research_study_id}")
                return

            # Create time-line for user, from initial trigger date
            qb_generator = ordered_qbs(user, research_study_id)
            user_qnrs = QNR_results(user, research_study_id)

            # Force recalculation of QNR->QB association if needed
            if user_qnrs.qnrs_missing_qb_association():
                user_qnrs.assign_qb_relationships(qb_generator=ordered_qbs)

            # As we move forward, capture state at each time point
            kwargs = {
                "user_id": user.id,
                "research_study_id": research_study_id,
            }

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
                        pending_qbts[-1].status == 'expired'):
                    # Found overlapping visits.  Move the expired date of
                    # previous just before start if possible
                    # (no additional rows with at dates > start)
                    other_status_after_next_start = False
                    for i in range(len(pending_qbts)-2, -1, -1):
                        # as we modify len of pending_qbts in special case below
                        # make sure next iteration is within new bounds
                        if i > len(pending_qbts)-1:
                            continue

                        unwanted_count = 0
                        if pending_qbts[i].at > start:
                            # Yet another special case to look for when the
                            # transition to new RP included an additional
                            # time-point (say month 33) that doesn't exist in
                            # the old RP.  This will appear as TWO overlapping
                            # QBs - one needing to be removed (say the old
                            # month 36) in favor of the skipped new (say
                            # month 33), and the last legit old one (say
                            # month 30) needing its endpoint adjusted
                            # further below.
                            remove_qb_id = pending_qbts[i].qb_id
                            remove_iteration = pending_qbts[i].qb_iteration
                            for j in range(i-1, -1, -1):
                                # keep looking back till we find the prev
                                if (
                                        pending_qbts[j].qb_id != remove_qb_id or
                                        pending_qbts[j].qb_iteration != remove_iteration):
                                    # unwanted_count represents all rows from
                                    # overlapped, unwanted visit
                                    unwanted_count = len(pending_qbts)-j-1
                                    break

                                # keep a lookout for work done in old RP
                                if pending_qbts[j].status in (
                                        'in_progress',
                                        'partially_completed',
                                        'completed'):
                                    other_status_after_next_start = True
                                    break

                            if other_status_after_next_start:
                                break  # from outer loop if set

                            # Remove unwanted from end of pending_qbts
                            if unwanted_count:
                                trace(
                                    "removing overlapping QBs: "
                                    f"{pending_qbts[-unwanted_count:]}")
                                del pending_qbts[-unwanted_count:]
                                continue

                        if pending_qbts[i].at < start:
                            break

                    if other_status_after_next_start:
                        current_app.logger.error(
                            "Overlap can't adjust previous as another event"
                            " occurred since subsequent (%s:%s) qb start for"
                            " user %d", qbd.qb_id, qbd.iteration, user_id)
                    else:
                        trace(f"moving overlapping date of {pending_qbts[-1]}")
                        pending_qbts[-1].at = start - relativedelta(seconds=1)
                        trace(f"  to {pending_qbts[-1]}")

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

                    last_posted_index = len(pending_qbts) - 1
                    if pending_qbts[-1].status == 'partially_completed':
                        # Look back further for status implying last posted
                        last_posted_index -= 1
                        if pending_qbts[last_posted_index].status != 'in_progress':
                            current_app.logger.warning(
                                "User %d has invalid QB timeline.  "
                                "Problematic qbd: %s", user_id, str(qbd))
                            continue

                    # Must double-check overlap; may no longer be true, if
                    # last_posted_index was one before...
                    if pending_qbts[last_posted_index].at > start:
                        # For questionnaires with common instrument names that
                        # happen to fit in both QBs, need to now reassign the
                        # QB associations as the second is getting tossed
                        use_qb_id = pending_qbts[last_posted_index].qb_id
                        use_qb_iter = pending_qbts[last_posted_index].qb_iteration
                        changed = user_qnrs.reassign_qb_association(
                            existing={
                                'qb_id': qbd.qb_id,
                                'iteration': qbd.iteration},
                            desired={
                                'qb_id': use_qb_id,
                                'iteration': use_qb_iter})

                        # IF the reassignment caused a change, AND the previous
                        # visit was in a partially_completed state AND the change
                        # now completes that visit, update the status.
                        if (
                                changed and
                                pending_qbts[-1].status == 'partially_completed'):
                            complete_date = user_qnrs.completed_date(
                                use_qb_id,
                                use_qb_iter)
                            if complete_date:
                                pending_qbts[-1].at = complete_date
                                pending_qbts[-1].status = 'completed'

                        # IF the reassignment caused a change, the persisted
                        # time from the first QB submission may be incorrect
                        # as the questionnaire that uniquely identifies the
                        # RP may have not been the first submission.
                        if changed:
                            # look back while still on correct visit for
                            # an in_progress, fix time if necessary
                            i = len(pending_qbts) - 1
                            while i > 0:
                                if not (
                                        pending_qbts[i].qb_id == use_qb_id and
                                        pending_qbts[i].qb_iteration == use_qb_iter):
                                    break
                                if pending_qbts[i].status == 'in_progress':
                                    pending_qbts[i].at = user_qnrs.earliest_result(
                                        use_qb_id, use_qb_iter)
                                    break
                                i -= 1

                        continue  # effectively removes the unwanted visit
                    else:
                        assert pending_qbts[-1].status == 'partially_completed'
                        assert pending_qbts[-1].at > start
                        # Move the partially completed event just prior to start
                        pending_qbts[-1].at = start - relativedelta(seconds=1)

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

            # If user withdrew from study, add a row marking the withdrawal
            # to the user's timeline, at the proper sequence.
            num_stored = 0
            _, withdrawal_date = consent_withdrawal_dates(
                user, research_study_id=research_study_id)
            if withdrawal_date:
                trace("withdrawn as of {}".format(withdrawal_date))
                j = 0
                for qbt in pending_qbts:
                    if qbt.at > withdrawal_date:
                        break
                    j += 1
                if j > 0:
                    # include visit in withdrawn for qb_status functionality
                    kwargs['qb_id'] = pending_qbts[j-1].qb_id
                    kwargs['qb_iteration'] = pending_qbts[j-1].qb_iteration
                    kwargs['qb_recur_id'] = pending_qbts[j-1].qb_recur_id
                store_rows = (
                    pending_qbts[0:j] +
                    [QBT(at=withdrawal_date, status='withdrawn', **kwargs)] +
                    pending_qbts[j:])
                check_for_overlaps(store_rows)
                db.session.add_all(store_rows)
                num_stored = len(store_rows)
            else:
                check_for_overlaps(pending_qbts)
                db.session.add_all(pending_qbts)
                num_stored = len(pending_qbts)

            if num_stored:
                auditable_event(
                    message="qb_timeline updated; {} rows".format(num_stored),
                    user_id=user_id, subject_id=user_id, context="assessment")
            db.session.commit()

            # With fresh calculation of a user's timeline, queue update of
            # user's adherence data as celery job
            kwargs = {
                'patient_id': user_id,
                'research_study_id': research_study_id}
            cache_single_patient_adherence_data.apply_async(
                kwargs=kwargs, queue=LOW_PRIORITY, retry=False)

    success = False
    for attempt in range(1, 6):
        try:
            attempt_update(user_id=user_id, research_study_id=research_study_id)
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
            self.redis = create_redis(current_app.config['REDIS_URL'])
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

    If no data is available for the user, `status` of `Not Yet Available` for
    the EMPRO study, `expired` for all others, as part of:
     {'status': 'expired', 'visit_name': None, 'action_state': 'not applicable'}

    :returns: dictionary with key/values for:
      status: string like 'expired'
      visit_name: for the period, i.e. '3 months'. ALWAYS in english, clients must translate
      action_state: 'not applicable', or status of follow-up action

    """
    from .research_study import EMPRO_RS_ID

    assert isinstance(research_study_id, int)
    assert isinstance(as_of_date, datetime)

    default_status = (
        "Not Yet Available" if research_study_id == EMPRO_RS_ID
        else OverallStatus.expired)
    results = {
        'status': default_status,
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
        # now that timelines are built beyond withdrawal, check for a
        # withdrawal row before the one found above
        withdrawn_qbt = (QBT.query.filter(QBT.user_id == user_id).filter(
            QBT.research_study_id == research_study_id).filter(
            QBT.at <= qbt.at).filter(
            QBT.status == OverallStatus.withdrawn)).first()
        if withdrawn_qbt:
            qbt = withdrawn_qbt

        results['status'] = qbt.status
        results['visit_name'] = visit_name(qbt.qbd())

        if research_study_id == EMPRO_RS_ID:
            # Not available to all products, thus the nested import
            from ..trigger_states.models import TriggerState

            # Don't include the most recent `due` as they hide
            # outstanding work, allowed till subsequent submission.
            ts = TriggerState.query.filter(
                TriggerState.user_id == user_id).filter(
                TriggerState.state != 'due').order_by(
                TriggerState.timestamp.desc()).first()
            if ts and ts.triggers:
                results['action_state'] = ts.triggers.get(
                    'action_state', 'required')
            else:
                results['action_state'] = 'not applicable'

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
