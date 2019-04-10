from datetime import datetime, MAXYEAR
from dateutil.relativedelta import relativedelta
from flask import current_app
from sqlalchemy.types import Enum as SQLA_Enum
import redis
from werkzeug.exceptions import BadRequest

from ..database import db
from ..date_tools import FHIR_datetime, RelativeDelta
from ..dogpile_cache import dogpile_cache
from ..timeout_lock import TimeoutLock
from ..trace import trace
from .overall_status import OverallStatus
from .qbd import QBD
from .questionnaire_bank import (
    qbs_by_rp,
    qbs_by_intervention,
    trigger_date,
    visit_name,
)
from .questionnaire_response import QNR_results
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

    # Zero to one RP makes things significantly easier - otherwise
    # swap in a strategy that can work with the change.
    rps = ResearchProtocol.assigned_to(user)

    if len(rps) > 0:
        # RP switch is delayed if user submitted any results for the then
        # active QB on the RP active at that time.
        user_qnrs = QNR_results(user)

        # With multiple RPs, move in lock step, determine when to switch.
        sorted_rps = sorted(
            list(rps), key=second_null_safe_datetime, reverse=True)

        # Start with oldest RP (current) till it's time to progress (next)
        current_rp, current_retired = sorted_rps.pop()
        if sorted_rps:
            trace("multiple RPs found")
            next_rp, next_retired = sorted_rps.pop()
        else:
            trace("single RP found")
            next_rp = None

        if sorted_rps:
            raise ValueError("can't cope with > 2 RPs at this time")

        if classification == 'indefinite':
            current_qbds = indef_qbs_by_rp(current_rp.id, trigger_date=td)
            next_rp_qbds = (
                indef_qbs_by_rp(next_rp.id, trigger_date=td) if next_rp else
                None)
        else:
            current_qbds = ordered_rp_qbs(current_rp.id, trigger_date=td)
            next_rp_qbds = (
                ordered_rp_qbs(next_rp.id, trigger_date=td) if next_rp else
                None)

        while True:
            # Advance both qb generators in sync while both RPs are defined
            try:
                current_qbd = next(current_qbds)
            except StopIteration:
                return
            if next_rp_qbds:
                try:
                    next_rp_qbd = next(next_rp_qbds)
                except StopIteration:
                    return
            users_start = calc_and_adjust_start(
                user=user, qbd=current_qbd, initial_trigger=td)
            users_expiration = calc_and_adjust_expired(
                user=user, qbd=current_qbd, initial_trigger=td)

            # if there's still a next and current gets retired before this
            # QB's expiration, switch over *unless* user submitted a matching
            # QNR on the current RP
            if (next_rp_qbds and current_retired < users_expiration and
                    not user_qnrs.earliest_result(
                        qb_id=current_qbd.questionnaire_bank.id,
                        iteration=current_qbd.iteration)):
                current_qbds = next_rp_qbds
                current_qbd, current_retired = next_rp_qbd, next_retired
                next_rp_qbds, next_retired = None, None
                users_start = calc_and_adjust_start(
                    user=user, qbd=current_qbd, initial_trigger=td)

            # done if user withdrew before the next start
            if withdrawal_date and withdrawal_date < users_start:
                trace("withdrawn as of {}".format(withdrawal_date))
                break

            current_qbd.relative_start = users_start
            # sanity check - make sure we don't adjust twice
            if hasattr(current_qbd, 'already_adjusted'):
                raise RuntimeError('already adjusted the qbd relative start')
            current_qbd.already_adjusted = True
            yield current_qbd
    else:
        trace("no RPs found")

        # Neither RP case hit, try intervention associated QBs
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
    # acquire a multiprocessing lock to prevent multiple requests
    # from duplicating rows during this slow process
    timeout = current_app.config.get("MULTIPROCESS_LOCK_TIMEOUT")
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
            raise ValueError("QB time line only applies to patients")

        # Create time line for user, from initial trigger date
        qb_generator = ordered_qbs(user)
        user_qnrs = QNR_results(user)

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
        _, withdrawal_date = consent_withdrawal_dates(user)
        if withdrawal_date:
            trace("withdrawn as of {}".format(withdrawal_date))
            store_rows = [
                qbt for qbt in pending_qbts if qbt.at < withdrawal_date]
            store_rows.append(
                QBT(at=withdrawal_date, status='withdrawn', **kwargs))
            db.session.add_all(store_rows)
        else:
            db.session.add_all(pending_qbts)

        db.session.commit()


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
