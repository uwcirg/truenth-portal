"""State machine implementation for EMPRO study triggers

See also:
    [IRONMAN EMPRO Study Experience](https://promowiki.movember.com/display/ISS/Product+Development+-+IRONMAN+EMPRO+Study)
"""
import copy
from datetime import datetime
from flask import current_app
from smtplib import SMTPRecipientsRefused
from statemachine import StateMachine, State
from statemachine.exceptions import TransitionNotAllowed

from .empro_domains import DomainManifold
from .empro_messages import patient_email, staff_emails
from .models import TriggerState
from ..database import db
from ..date_tools import FHIR_datetime
from ..models.qb_status import QB_Status
from ..models.qbd import QBD
from ..models.questionnaire_bank import QuestionnaireBank
from ..models.user import User
from ..timeout_lock import LockTimeout, TimeoutLock

EMPRO_STUDY_ID = 1
EMPRO_LOCK_KEY = "empro-trigger-state-lock-{user_id}"


class EMPRO_state(StateMachine):
    """States a user repeatedly transitions through as an EMPRO participant

    States:
      - unstarted: generic pre-state; user can't yet start an EMPRO
       questionnaire.
      - due: user has completed prerequisites or the next cycle just became
       available, which displaces existing triggers, at least temporarily.
      - inprocess: system in process of evaluating users triggers
      - processed: user's completed EMPRO questionnaire(s) have been
       processed.  a list of hard and soft triggers are available.
      - triggered: action taken on user's trigger state, such as email
       sent to subject and staff as appropriate.  if no further action is
       necessary, transition immediately to ``resolved``.  a list of
       hard and soft triggers are available.
      - resolved: no further action needed.  a list of hard and soft
       triggers are available.

    Transitions:
      - initially_available: called when a user qualifies for the study
      - begin_process: called on QNR submission, initiating processing
      - processed_triggers: processing of results completed; trigger state
       available
      - fired_events: trigger state has been evaluated, events (such as
       generating email for clinicians and patients) have fired.
      - resolve: actions complete, nothing pending for trigger state
      - next_available: called once the next EMPRO cycle becomes available

    """

    # States
    unstarted = State('unstarted', initial=True)
    due = State('due')
    inprocess = State('inprocess')
    processed = State('processed')
    triggered = State('triggered')
    resolved = State('resolved')

    # Transitions
    initial_available = unstarted.to(due)
    begin_process = due.to(inprocess)
    processed_triggers = inprocess.to(processed)
    fired_events = processed.to(triggered)
    resolve = triggered.to(resolved)
    next_available = resolved.to(due)


def enter_user_trigger_critical_section(user_id):
    """Set semaphore noting users trigger state is actively being processed

    A number of asynchronous tasks are involved in processing a users results
    and determining their trigger state.  This endpoint is used to set the
    semaphore used by other parts of the system to determine if results are
    available or still pending.

    :raises AsyncLockUnavailable: if lock for user is already present
    :raises TransitionNotAllowed: if user's current trigger state won't allow
      a transition to the ``inprocess`` state.

    """
    ts = users_trigger_state(user_id)
    sm = EMPRO_state(ts)
    sm.begin_process()
    # Record the historical transformation via insert.
    current_app.logger.debug(
        "record state change to 'inprocess' from "
        f"enter_user_trigger_critical_section({user_id})")
    ts.insert(from_copy=True)

    # Now 'inprocess', obtain the lock to be freed at the conclusion
    # of `evaluate_triggers()`
    critical_section = TimeoutLock(key=EMPRO_LOCK_KEY.format(user_id=user_id))
    critical_section.__enter__()


def users_trigger_state(user_id):
    """Obtain latest trigger state for given user

    Returns latest TriggerState row for user or creates transient if not
     found.

    :returns TriggerState: with ``state`` attribute meaning:
      - unstarted: no info avail for user
      - due: users triggers unavailable; assessment due
      - inprocess: triggers are not ready; continue to poll for results
      - processed: triggers available in TriggerState.triggers attribute
      - triggered: triggers available in TriggerState.triggers attribute

    """
    # if semaphore is locked for user, return "inprocess"
    semaphore = TimeoutLock(key=EMPRO_LOCK_KEY.format(user_id=user_id))
    if semaphore.is_locked():
        return TriggerState(user_id=user_id, state='inprocess')

    ts = TriggerState.query.filter(
        TriggerState.user_id == user_id).order_by(
        TriggerState.timestamp.desc()).first()
    if not ts:
        ts = TriggerState(user_id=user_id, state='unstarted')
    return ts


def initiate_trigger(user_id):
    """Call when EMPRO becomes available for user or next is due"""
    ts = users_trigger_state(user_id)
    if ts.state == 'due':
        # Allow idempotent call - skip out if in correct state
        return ts

    # Check and update the status of pending work.
    if ts.state == 'triggered':
        sm = EMPRO_state(ts)
        sm.resolve()
        db.session.commit()

    if ts.state == 'resolved':
        next_visit = int(ts.visit_month) + 1
        current_app.logger.debug(f"transition to next due for {user_id}")
        # generate a new ts, to leave resolved record behind
        ts = TriggerState(user_id=user_id, state='unstarted')
        ts.visit_month = next_visit

    sm = EMPRO_state(ts)
    sm.initial_available()

    # Record the historical transformation via insert
    if ts.id is None:
        current_app.logger.debug("record state change to 'due' for {user_id}")
        ts.insert()
    return ts


def evaluate_triggers(qnr, override_state=False):
    """Process state for given QuestionnaireResponse

    Complicated set of business rules used to determine trigger state.
    Look to the user's other QuestionnaireResponses and Observations
    generated to determine user's trigger state for each respective
    response period.

    Business rules defined at:
     https://promowiki.movember.com/display/ISS/Trigger+Logic

    :param qnr: QuestionnaireResponse to process as "current"
    :return: None

    """
    if qnr.status != 'completed':
        raise ValueError(
            f"QuestionnaireResponse: {qnr.id} with status: {qnr.status} "
            "sent to evaluate_triggers, only 'completed' are eligible")

    try:
        # first, confirm state transition is allowed - raises if not
        ts = users_trigger_state(qnr.subject_id)
        sm = EMPRO_state(ts)

        if ts.state == 'processed' and override_state:
            # go around state machine, setting directly when requested
            current_app.logger.debug(
                f"override trigger_state transition from {ts.state} "
                f"to 'inprocess'")
            ts.state = 'inprocess'

        # typical flow, processing was triggered before SDC handoff
        # if launched from testing or some catch-up task, initiate now
        if ts.state != "inprocess":
            current_app.logger.debug(
                "evaluate_triggers(): trigger_state transition from "
                f"{ts.state} to 'inprocess'")
            enter_user_trigger_critical_section(user_id=qnr.subject_id)
            # confirm local vars picked up state change
            assert ts.state == 'inprocess'

        # bring together and evaluate available data for triggers
        dm = DomainManifold(qnr)
        ts.triggers = dm.eval_triggers()
        ts.questionnaire_response_id = qnr.id

        # transition and persist state
        sm.processed_triggers()
        current_app.logger.debug(
            "record state change to 'processed' from "
            f"evaluate_triggers() for {qnr.subject_id}")
        ts.insert(from_copy=True)

        # a submission closes the window of availability for the
        # post-intervention clinician follow up.  mark state if
        # one is found
        previous = TriggerState.query.filter(
            TriggerState.user_id == qnr.subject_id).filter(
            TriggerState.state == 'resolved').order_by(
            TriggerState.timestamp.desc()).first()
        if previous and previous.triggers.get('action_state') not in (
                'completed', 'missed', 'not applicable'):
            triggers = copy.deepcopy(previous.triggers)
            triggers['action_state'] = 'missed'
            previous.triggers = triggers
            db.session.commit()

        return ts

    except (TransitionNotAllowed, LockTimeout) as e:
        current_app.logger.exception(e)
        raise e

    finally:
        # All done, release semaphore for this user
        critical_section = TimeoutLock(key=EMPRO_LOCK_KEY.format(
            user_id=qnr.subject_id))
        critical_section.__exit__(None, None, None)


def fire_trigger_events():
    """Typically called as a celery task, fire any pending events

    After questionnaire responses and resulting observations are evaluated,
    a celery job call lands here to seek out and execute any appropriate
    events from the user's trigger state.  Said rows will be in the
    'processed' state.

    Actions are recorded in trigger_states.triggers and the row's state
    is transitioned to 'triggered' or should no further action be necessary,
    'resolved'.

    """
    def send_n_report(em, context, record):
        """Send email, append success/fail w/ context to record"""
        result = {'context': context, 'timestamp': FHIR_datetime.now()}
        try:
            em.send_message()
            db.session.add(em)
            db.session.commit()
            result['email_message_id'] = em.id
            record.append(result)
        except SMTPRecipientsRefused as e:
            msg = ("Error sending trigger email to {}: "
                   "{}".format(em.recipients, e))
            current_app.logger.errors(msg)
            result['error'] = msg
            record.append(result)

    # as a job, make sure only running one concurrent instance
    NEVER_WAIT = 0
    with TimeoutLock(key='fire_trigger_events', timeout=NEVER_WAIT):
        # seek out any pending "processed" work, i.e. triggers recently
        # evaluated
        for ts in TriggerState.query.filter(TriggerState.state == 'processed'):
            # necessary to make deep copy in order to update DB JSON
            triggers = copy.deepcopy(ts.triggers)
            triggers['action_state'] = 'not applicable'
            triggers['actions'] = dict()
            triggers['actions']['email'] = list()

            # Emails generated for both patient and clinician/staff based
            # on hard triggers.  Patient gets 'thank you' email regardless.
            hard_triggers = ts.hard_trigger_list()
            soft_triggers = ts.soft_trigger_list()
            pending_emails = []
            patient = User.query.get(ts.user_id)

            # Patient always gets mail
            pending_emails.append((
                patient_email(patient, soft_triggers, hard_triggers),
                "patient thank you"))

            if hard_triggers:
                triggers['action_state'] = 'required'

                # In the event of hard_triggers, clinicians/staff get mail
                for msg in staff_emails(patient, hard_triggers, True):
                    pending_emails.append((msg, "initial staff alert"))

            for em, context in pending_emails:
                send_n_report(em, context, triggers['actions']['email'])

            # Change state, as this row has been processed.
            ts.triggers = triggers
            sm = EMPRO_state(ts)
            sm.fired_events()

            # Without hard triggers, no further action is necessary
            if not hard_triggers:
                sm.resolve()

        db.session.commit()

        # Now seek out any pending actions, such as reminders to staff
        now = datetime.utcnow()
        for ts in TriggerState.query.filter(
                TriggerState.state.in_(('triggered', 'resolved'))):
            # Need to consider state == resolved, as the user may
            # have a newer EMPRO due, but the previous still hasn't
            # received a post intervention QB from staff, noted by
            # the action_state:
            if (
                    'action_state' not in ts.triggers or
                    ts.triggers['action_state'] in (
                    'completed', 'missed', 'not applicable')):
                continue

            assert ts.triggers['action_state'] in ('required', 'overdue')
            patient = User.query.get(ts.user_id)

            # Withdrawn users should never receive reminders, nor staff
            # about them.
            qb_status = QB_Status(
                user=patient, research_study_id=EMPRO_STUDY_ID, as_of_date=now)
            if qb_status.withdrawn_by(now):
                continue

            if ts.reminder_due():
                pending_emails = staff_emails(
                    patient, ts.hard_trigger_list(), False)

                # necessary to make deep copy in order to update DB JSON
                triggers = copy.deepcopy(ts.triggers)
                triggers['action_state'] = 'overdue'
                for em in pending_emails:
                    send_n_report(
                        em, context="reminder staff alert",
                        record=triggers['actions']['email'])

                # push updated record back into trigger_states
                ts.triggers = triggers

        db.session.commit()


def empro_staff_qbd_accessor(qnr):
    """Specialized closure for QNR association

    When QNRs are posted (or other events such as a user's consent date
    changes), the QNR needs to be associated with the appropriate
    QuestionnarieBank (and iteration).

    This function returns a closure to function like the lookup
    for other questionnaire banks.

    """
    # with qnr captured, return a function capable of looking up
    # the appropriate QB/Iteration when called.

    def qbd_accessor(as_of_date, classification, instrument):
        """Implement qbd_accessor API for EMPRO Staff QB

        Look up appropriate QB/Iteration for subject from given as_of_date.
        Using the trigger_states for user, determine best match.

        Stores the QNR_id on the respective trigger_state, if a good match
        is found.

        :returns: qbd (questionnaire bank details) representing QB and iteration
         for QNR association.

        """
        result = QBD(None, None)
        no_match_message = (
            "EMPRO Staff qnr association lookup failed for subject "
            f"{qnr.subject_id} @ {as_of_date}")

        if classification == 'indefinite':
            # Doesn't apply - leave
            return result
        if instrument != 'ironman_ss_post_tx':
            raise ValueError(
                "specialized QBD accessor given wrong instrument "
                f"{instrument}")

        # find best match from subject's trigger_states.  will be in
        # `triggered` state if current, or `resolved` if time has
        # passed and the user now has the subsequent month due.
        query = TriggerState.query.filter(
            TriggerState.user_id == qnr.subject_id).filter(
            TriggerState.state.in_(('triggered', 'resolved'))).order_by(
            TriggerState.timestamp)
        if not query.count():
            current_app.logger.errors(no_match_message)
            return result

        match = None
        for ts in query:
            if ts.timestamp < as_of_date:
                match = ts
            if ts.timestamp > as_of_date:
                # A patient's submission beyond the date of the POST Tx QB
                # doesn't make sense - break out.
                break

        if not match:
            current_app.logger.error(no_match_message)
            return result

        # Store the match and advance the state if necessary
        triggers = copy.deepcopy(match.triggers)
        triggers['action_state'] = 'completed'

        # Business rule to prevent multiple submissions (TN-2848)
        if ('resolution' in triggers and
                triggers['resolution']['qnr_id'] != qnr.id):
            current_app.logger.error(
                f"Second POST-TX response {qnr.id} not allowed on "
                f"user {qnr.subject_id}")
            return result

        triggers['resolution'] = {
            'qnr_id': qnr.id,
            'qb_iteration': None,
            'authored': qnr.document['authored']}
        match.triggers = triggers
        if match.state != 'resolved':
            sm = EMPRO_state(match)
            sm.resolve()
        db.session.commit()

        # Look up post tx match WRT source qb
        if not triggers['source']['qb_id']:
            raise ValueError("association not possible w/o source QB")

        src_qb = QuestionnaireBank.query.get(triggers['source']['qb_id'])
        if 'baseline' in src_qb.name:
            post_tx_qb = QuestionnaireBank.query.filter(
                QuestionnaireBank.name == 'ironman_ss_post_tx_baseline'
            ).one()
        else:
            post_tx_qb = QuestionnaireBank.query.filter(
                QuestionnaireBank.name ==
                'ironman_ss_post_tx_recurring_monthly_pattern'
            ).one()

        result.relative_start = match.timestamp
        result.qb_id = post_tx_qb.id
        result.iteration = triggers['source']['qb_iteration']
        return result
    return qbd_accessor
