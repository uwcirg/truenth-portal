"""State machine implementation for EMPRO study triggers

See also:
    [IRONMAN EMPRO Study Experience](https://promowiki.movember.com/display/ISS/Product+Development+-+IRONMAN+EMPRO+Study)
"""
import copy
from datetime import datetime, timedelta
from flask import current_app
from requests import post
from smtplib import SMTPRecipientsRefused
from statemachine import StateMachine, State
from statemachine.exceptions import TransitionNotAllowed

from .empro_domains import DomainManifold
from .empro_messages import invite_email, patient_email, staff_emails
from .models import TriggerState, opt_out_this_visit_key
from ..database import db
from ..date_tools import FHIR_datetime
from ..models.qb_status import QB_Status
from ..models.qbd import QBD
from ..models.questionnaire_bank import QuestionnaireBank
from ..models.questionnaire_response import QuestionnaireResponse
from ..models.observation import Observation
from ..models.research_study import EMPRO_RS_ID, withdrawn_from_research_study
from ..models.user import User
from ..timeout_lock import TimeoutLock, LockTimeout

EMPRO_LOCK_KEY = "empro-trigger-state-lock-{user_id}"
OPT_OUT_DELAY = 1800  # seconds to allow user to provide opt-out choices

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

    NB: for "skipped" visits, we never transition out of `due`, but rather
    update the visit_month.

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


def users_trigger_state(user_id, as_of_date=None):
    """Obtain the latest trigger state for given user

    Returns latest TriggerState row for user or creates transient if current
     visit_month not found.  NB: beyond end of study or withdrawal, the last
     valid is returned.

    :returns TriggerState: with ``state`` attribute meaning:
      - unstarted: no info avail for user
      - due: users triggers unavailable; assessment due
      - inprocess: triggers are not ready; continue to poll for results
      - processed: triggers available in TriggerState.triggers attribute
      - triggered: triggers available in TriggerState.triggers attribute

    """
    if as_of_date is None:
        as_of_date = datetime.utcnow()

    vm = lookup_visit_month(user_id, as_of_date)
    ts = None
    withdrawal_date = withdrawn_from_research_study(user_id, EMPRO_RS_ID)
    rows = TriggerState.query.filter(
        TriggerState.user_id == user_id).order_by(
        TriggerState.timestamp.desc())
    for ts_row in rows:
        # most recent with a timestamp prior to as_of_date, in case this is a rebuild
        if as_of_date < ts_row.timestamp:
            continue
        ts = ts_row
        if ts.visit_month < vm and not withdrawal_date:
            current_app.logger.debug(
                f"{user_id} trigger state out of sync for visit {vm} (found {ts.visit_month})")
            # unset ts given wrong month, to pick up below
            ts = None
        break

    if not ts:
        ts = TriggerState(
            user_id=user_id, state='unstarted', timestamp=as_of_date, visit_month=vm)

    return ts


def lookup_visit_month(user_id, as_of_date):
    """Helper to determine what visit month qb_timeline has for user"""
    from ..models.qb_timeline import qb_status_visit_name
    status = qb_status_visit_name(user_id, EMPRO_RS_ID, as_of_date)
    visit_name = status['visit_name']
    if visit_name is None:
        return 0
    one_index = int(visit_name.split()[1])
    return one_index - 1


def initiate_trigger(user_id, as_of_date=None, rebuilding=False):
    """Call when EMPRO becomes available for user or next is due"""
    if as_of_date is None:
        as_of_date = datetime.utcnow()

    ts = users_trigger_state(user_id)
    if ts.state == 'due':
        # Possible the user took no action, as in skipped the last month
        # (or multiple months may have been skipped if time-warping).
        # If so, the visit_month and timestamp are updated on the last
        # `due` row that was found above.
        visit_month = lookup_visit_month(user_id, as_of_date)
        if ts.visit_month != visit_month:
            current_app.logger.warn(f"{user_id} skipped EMPRO visit {ts.visit_month}")
            ts.visit_month = visit_month
            ts.timestamp = as_of_date
            db.session.commit()

        # Allow idempotent call - skip out if in correct state
        return ts

    # Check and update the status of pending work.
    if ts.state == 'triggered':
        sm = EMPRO_state(ts)
        sm.resolve()
        db.session.commit()

    if ts.state == 'resolved':
        next_visit = int(ts.visit_month) + 1
        current_app.logger.debug(f"transition from {ts} to next due")
        # generate a new ts, to leave resolved record behind
        ts = TriggerState(user_id=user_id, state='unstarted', timestamp=as_of_date)
        ts.visit_month = next_visit
        current_app.logger.debug(
            "persist-trigger_states-new from initiate_trigger(), "
            f"resolved clause {ts}")

    sm = EMPRO_state(ts)
    sm.initial_available()

    # Record the historical transformation via insert
    if ts.id is None:
        ts.insert()
        current_app.logger.debug(
            "persist-trigger_states-new from initiate_trigger(),"
            f"record historical clause {ts}")

    # TN-2863 auto send invite when first available, unless rebuilding
    if ts.visit_month == 0 and not rebuilding:
        invite_email(User.query.get(user_id))

    db.session.commit()
    return ts


def evaluate_triggers(qnr):
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

        # include previous month resolved row, if available
        query = TriggerState.query.filter(
            TriggerState.user_id == qnr.subject_id).filter(
            TriggerState.state.in_(('resolved', 'triggered', 'processed'))).filter(
            TriggerState.visit_month == ts.visit_month - 1)
        previous = query.first()

        # bring together and evaluate available data for triggers
        dm = DomainManifold(qnr)
        previous_triggers = previous.triggers if previous else None
        ts.triggers = dm.eval_triggers(previous_triggers)
        ts.questionnaire_response_id = qnr.id

        # transition and persist state
        sm.processed_triggers()
        ts.insert(from_copy=True)
        current_app.logger.debug(
            "persist-trigger_states-new record state change to 'processed' "
            f"from evaluate_triggers() {ts}")
        return ts

    except TransitionNotAllowed as e:
        current_app.logger.exception(e)
        raise e


def fire_trigger_events():
    """Typically called as a celery task, fire any pending events

    After questionnaire responses and resulting observations are evaluated,
    a celery job call lands here to seek out and execute any appropriate
    events from the user's trigger state.  Said rows will be in the
    'processed' state.

    NB, the opt-out feature requires a user has adequate time to provide
    feedback (user-input).  Therefore, if the set of triggers has at least
    one domain for which opt-out may apply, skip over processing that one
    until opt-out results are present, or the OPT_OUT_DELAY has expired.

    Actions are recorded in trigger_states.triggers and the row's state
    is transitioned to 'triggered' or should no further action be necessary,
    'resolved'.

    """
    now = datetime.utcnow()

    def delay_processing(ts):
        current_app.logger.debug("QQQ enter sequential_threshold_reached")
        """Give user time to respond to opt-out prompt if applicable"""
        if not ts.sequential_threshold_reached():
            # not applicable unless at least one domain has adequate count
            current_app.logger.debug("QQQ sequential_threshold_reached false, bail")
            return

        if ts.opted_out_domains():
            # user must have already replied, if opted out of at least one
            current_app.logger.debug("QQQ user already opted out")
            return

        # check time since row transitioned to current state.  delay
        # till threshold reached
        current_app.logger.debug(f"QQQ row timestamp: {ts.timestamp} now: {datetime.utcnow()}")
        current_app.logger.debug(f"QQQ row + delay {ts.timestamp + timedelta(seconds=OPT_OUT_DELAY)}")
        current_app.logger.debug(f"QQQ tzinfo: {ts.timestamp.tzinfo} tz2: {(ts.timestamp + timedelta(seconds=OPT_OUT_DELAY)).tzinfo} tz3: {datetime.utcnow().tzinfo}")
        if ts.timestamp < timedelta(seconds=OPT_OUT_DELAY) + datetime.utcnow():
            current_app.logger.debug(f"QQQ return True from delay_processing")
            return True

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
            current_app.logger.error(msg)
            result['error'] = msg
            record.append(result)

    def process_processed(ts):
        """Process an individual trigger_states row in the processed state"""
        # necessary to make deep copy in order to update DB JSON
        triggers = copy.deepcopy(ts.triggers)
        triggers['action_state'] = 'not applicable'
        triggers['actions'] = dict()
        triggers['actions']['email'] = list()

        # Emails generated for both patient and clinician/staff based
        # on hard triggers.  Patient gets 'thank you' email regardless.
        hard_triggers = ts.hard_trigger_list()
        soft_triggers = ts.soft_trigger_list()
        opted_out = ts.opted_out_domains()
        actionable_triggers = list(set(hard_triggers) - set(opted_out))
        # persist all opted out for front-end use as well
        for domain, link_triggers in triggers['domain'].items():
            if domain in opted_out:
                link_triggers[opt_out_this_visit_key] = True

        pending_emails = []
        patient = User.query.get(ts.user_id)

        # Patient always gets mail
        if patient.email_ready()[0]:
            pending_emails.append((
                patient_email(patient, soft_triggers, hard_triggers),
                "patient thank you"))
        else:
            current_app.logger.error(
                f"EMPRO Patient({patient.id}) w/o email!  Can't send message")

        if hard_triggers:
            if actionable_triggers:
                triggers['action_state'] = 'required'
            # In the event of hard_triggers, clinicians/staff get mail
            for msg in staff_emails(patient, hard_triggers, opted_out, True):
                pending_emails.append((msg, "initial staff alert"))

        for em, context in pending_emails:
            send_n_report(em, context, triggers['actions']['email'])

        # Change state, as this row has been processed.
        ts.triggers = triggers
        sm = EMPRO_state(ts)
        sm.fired_events()

        # Without actionable triggers, no further action is necessary
        if not actionable_triggers:
            sm.resolve()

        current_app.logger.debug(
            f"persist-trigger_states-change from fire_trigger_events() {ts}")

    def process_pending_actions(ts):
        """Process a trigger states row needing subsequent action"""

        if (
                'action_state' not in ts.triggers or
                ts.triggers['action_state'] in (
                'completed', 'missed', 'not applicable',
                'withdrawn')):
            return

        if ts.triggers['action_state'] not in ('required', 'overdue'):
            raise ValueError(
                f"Invalid action_state {ts.triggers['action_state']} "
                f"for patient {ts.user_id}")

        patient = User.query.get(ts.user_id)

        # Withdrawn users should never receive reminders, nor staff
        # about them.
        qb_status = QB_Status(
            user=patient, research_study_id=EMPRO_RS_ID, as_of_date=now)
        if qb_status.withdrawn_by(now):
            triggers = copy.deepcopy(ts.triggers)
            triggers['action_state'] = 'withdrawn'
            ts.triggers = triggers
            current_app.logger.debug(
                f"persist-trigger_states-change withdrawn clause {ts}")
            return

        if ts.reminder_due():
            pending_emails = staff_emails(
                patient, ts.hard_trigger_list(), ts.opted_out_domains(), False)

            # necessary to make deep copy in order to update DB JSON
            triggers = copy.deepcopy(ts.triggers)
            triggers['action_state'] = 'overdue'
            for em in pending_emails:
                send_n_report(
                    em, context="reminder staff alert",
                    record=triggers['actions']['email'])

            # push updated record back into trigger_states
            ts.triggers = triggers
            current_app.logger.debug(
                f"persist-trigger_states-change reminder_due clause {ts}")

    # Main loop for this task function.
    #
    # As this is a recurring, scheduled job, simply skip over any locked keys
    # to pick up next run.
    #
    # The per-user lock also is checked elsewhere (key=EMPRO_LOCK_KEY(user_id)),
    # to prevent concurrent state transitions on a given user.
    NEVER_WAIT = 0

    # seek out any pending "processed" work, i.e. triggers recently
    # evaluated
    for ts in TriggerState.query.filter(TriggerState.state == 'processed'):
        current_app.logger.debug("QQQ call delay_processing")
        if delay_processing(ts):
            continue
        current_app.logger.debug("QQQ delay_processing didn't work")
        try:
            with TimeoutLock(
                    key=EMPRO_LOCK_KEY.format(user_id=ts.user_id),
                    timeout=NEVER_WAIT):
                process_processed(ts)
                db.session.commit()
        except LockTimeout:
            # will get picked up next scheduled run - ignore
            pass

        # Now seek out any pending actions, such as reminders to staff
        for ts in TriggerState.query.filter(TriggerState.state == 'triggered'):
            try:
                with TimeoutLock(
                        key=EMPRO_LOCK_KEY.format(user_id=ts.user_id),
                        timeout=NEVER_WAIT):
                    process_pending_actions(ts)
                    db.session.commit()
            except LockTimeout:
                # will get picked up next scheduled run - ignore
                pass


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
            current_app.logger.error(no_match_message)
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
                f"Second POST-TX response {qnr.id} not allowed on {match}")
            return result

        triggers['resolution'] = {
            'qnr_id': qnr.id,
            'qb_iteration': None,
            'authored': qnr.document['authored']}
        match.triggers = triggers
        if match.state != 'resolved':
            sm = EMPRO_state(match)
            sm.resolve()
        current_app.logger.debug(
            f"persist-trigger_states-change from qbd_accessor {match}")
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


def extract_observations(questionnaire_response_id, override_state=False):
    """Submit QNR to SDC service; store returned Observations

    :param questionnaire_response_id:  QNR to process
    :param override_state: set to override transition exceptions.  This
      is only used in exceptional cases, such as re-processing one that
      was previously interrupted and left in the `inprocess` state.
    :return: None
    """
    qnr = QuestionnaireResponse.query.get(questionnaire_response_id)

    # given asynchronous possibility, require user's EMPRO lock
    with TimeoutLock(
            key=EMPRO_LOCK_KEY.format(user_id=qnr.subject_id), timeout=60):
        ts = users_trigger_state(qnr.subject_id)
        sm = EMPRO_state(ts)
        if not override_state:
            sm.begin_process()

            # Record the historical transition via insert, w/ qnr just in case
            # SDC service isn't available, or some other exception
            ts.questionnaire_response_id = qnr.id
            ts.insert(from_copy=True)
            current_app.logger.debug(
                "persist-trigger_states-new from"
                f" enter_user_trigger_critical_section() {ts}")

            # As we now have a new EMPRO to score, clean up any unfinished
            # rows, as they can no longer be acted on.
            ts.resolve_outstanding(ts.visit_month)

        if not ts.state == 'inprocess':
            raise ValueError(
                f"invalid state; can't score: {qnr.subject_id}:{qnr.id}")

        qnr_json = qnr.as_sdc_fhir()

        SDC_BASE_URL = current_app.config['SDC_BASE_URL']
        response = post(f"{SDC_BASE_URL}/$extract", json=qnr_json)
        response.raise_for_status()

        # Add SDC generated observations to db
        Observation.parse_obs_bundle(response.json())
        db.session.commit()

        # With completed scoring, evaluate for triggers
        evaluate_triggers(qnr)

    # Finally, fire any outstanding actions
    # NB async locks obtained w/i
    fire_trigger_events()
