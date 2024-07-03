from copy import deepcopy
from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import make_transient

from ..database import db
from ..date_tools import FHIR_datetime, weekday_delta
from ..models.audit import Audit

opt_out_this_visit_key = '_opt_out_this_visit'


trigger_state_enum = ENUM(
    'unstarted',
    'due',
    'inprocess',
    'processed',
    'triggered',
    'resolved',
    name='trigger_state_type',
    create_type=False)


class TriggerState(db.Model):
    """ORM class for trigger state

    Model patient's trigger state, retaining historical record for reporting.

    """
    __tablename__ = 'trigger_states'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False, index=True)
    state = db.Column('state', trigger_state_enum, nullable=False, index=True)
    timestamp = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    questionnaire_response_id = db.Column(
        db.ForeignKey('questionnaire_responses.id'), index=True)
    visit_month = db.Column(db.Integer, nullable=False, index=True, default=0)
    triggers = db.Column(JSONB)

    __table_args__ = (
        UniqueConstraint(
            user_id, state, visit_month,
            name='_trigger_states_user_state_visit_month'),
    )

    def as_json(self):
        results = {
            'state': self.state,
            'user_id': self.user_id,
            'visit_month': self.visit_month}
        if self.timestamp:
            results['timestamp'] = FHIR_datetime.as_fhir(self.timestamp)
        if self.triggers:
            results['triggers'] = self.triggers
        return results

    def __repr__(self):
        return (
            f"TriggerState on user {self.user_id}: {self.state} "
            f"month: {self.visit_month}")

    def insert(self, from_copy=False):
        """Shorthand to create/persist a new row as defined

        :param from_copy: set when an existing row was copied/used to
         force generation of new row.

        """
        if self.id and not from_copy:
            raise RuntimeError(f"'{self}' already persisted - can't continue")
        if from_copy:
            # Force new row with db defaults for id and timestamp
            make_transient(self)
            self.id = None
            self.timestamp = None
        db.session.add(self)
        db.session.commit()
        # following a potential make_transient call, must reload the row
        # as we intentionally reset the id (to pick up the next in sequence)
        # and the session.commit() clears all associated object state
        # see https://github.com/sqlalchemy/sqlalchemy/issues/3640
        self = db.session.merge(self)

    def apply_opt_out(self, opt_out_dict):
        """Given JSON dict with opt_out domains, apply to self.triggers

        The format of the expected JSON can be found in:
          tests/fixtures/trigger_state.py::opt_out_submission

        :raise ValueError: if problems found with validating incoming JSON
          or self.triggers isn't defined
        :returns: modified self
        """
        if not self.triggers:
            raise ValueError(
                f"{self.user_id} has no triggers for {self.visit_month}; "
                "can't apply opt_out as requested")
        if not opt_out_dict:
            raise ValueError("missing required JSON doc")
        if opt_out_dict.get('user_id') != self.user_id:
            raise ValueError(f"user_id({self.user_id} not in opt_out: {opt_out_dict}")
        if opt_out_dict.get('visit_month') != self.visit_month:
            raise ValueError(
                f"user_id({self.user_id} visit_month({self.visit_month}) "
                f"not in opt_out: {opt_out_dict}")

        opt_out_of_domains = set()
        for d, vals in opt_out_dict['triggers']['domains'].items():
            if vals.get(opt_out_this_visit_key) is True:
                opt_out_of_domains.add(d)

        if not opt_out_of_domains:
            # no changes to persist
            return self

        tc = deepcopy(self.triggers)
        for domain, link_triggers in tc['domain'].items():
            if domain in opt_out_of_domains:
                link_triggers[opt_out_this_visit_key] = True
            elif opt_out_this_visit_key in link_triggers:
                link_triggers.pop(opt_out_this_visit_key)

        # Given the business rule to only allow 3 total opt-outs, bump counts
        # which requires full trigger history
        total_opt_outs_by_domain = {domain: 1 for domain in opt_out_of_domains}
        previous_visits = TriggerState.query.filter(
            TriggerState.visit_month < self.visit_month).filter(
            TriggerState.user_id == self.user_id).filter(
            TriggerState.state == 'resolved').order_by(
            TriggerState.visit_month)

        for row in previous_visits:
            # accumulate counts of previous opt-outs for current request
            for domain, link_triggers in row.triggers['domain'].items():
                if domain not in opt_out_of_domains:
                    continue
                if link_triggers.get(opt_out_this_visit_key, False):
                    total_opt_outs_by_domain[domain] += 1

        for domain, count in total_opt_outs_by_domain.items():
            tc['domain'][domain]['_total_opted_out'] = count

        self.triggers = tc
        return self

    def hard_trigger_list(self):
        """Convenience function to return list of hard trigger domains

        Save clients from internal structure of self.triggers - returns
        a simple list of hard trigger domains if any exist for instance.

        """
        if not self.triggers:
            return

        results = []
        for domain, link_triggers in self.triggers['domain'].items():
            if 'hard' in link_triggers.values():
                results.append(domain)
        return sorted(results)

    def opted_out_domains(self):
        """Convenience function to return list of opted out visit domains

        :returns: list of domains user opted out of on current visit, or empty list.
        """
        results = []
        if not self.triggers:
            return results

        results = []
        for domain, link_triggers in self.triggers['domain'].items():
            if opt_out_this_visit_key in link_triggers:
                results.append(domain)
        return sorted(results)

    def sequential_threshold_reached(self):
        """Returns True IFF at least one domain above sequential threshold

        Business rule says when >= 3 sequential hard triggers for a given
        domain are achieved, the user gets the option to opt-out of follow
        up from clinician.  This convenience method looks through all domains
        in triggers to see if at least one has adequate sequential count of
        hard triggers.

        :returns: True if at least one domain has adequate sequential hard triggers
        """
        from .empro_domains import sequential_hard_trigger_count_key
        if not self.triggers:
            return

        for domain, link_triggers in self.triggers['domain'].items():
            if link_triggers.get(sequential_hard_trigger_count_key, 0) > 2:
                return True

    def reminder_due(self, as_of_date=None):
        """Determine if reminder is due from internal state"""
        # locate first and most recent *staff* email
        first_sent, last_sent = None, None
        for email in self.triggers['actions']['email']:
            if 'staff' in email['context']:
                if not first_sent:
                    first_sent = FHIR_datetime.parse(email['timestamp'])
                last_sent = FHIR_datetime.parse(email['timestamp'])

        if not first_sent:
            return

        if not as_of_date:
            as_of_date = datetime.utcnow()

        # To be sent daily after the initial 48 hours
        needed_delta = timedelta(days=1)
        if first_sent + timedelta(hours=1) > last_sent:
            # only initial has been sent.  need 48 hours to have passed
            needed_delta = timedelta(days=2)

        return weekday_delta(last_sent, as_of_date) >= needed_delta

    def soft_trigger_list(self):
        """Convenience function to return list of soft trigger domains

        Save clients from internal structure of self.triggers - returns
        a simple list of soft trigger domains if any exist for instance.
        NB, all hard triggers imply a matching soft trigger.

        """
        if not self.triggers:
            return

        results = set(self.hard_trigger_list())
        for domain, link_triggers in self.triggers['domain'].items():
            if 'soft' in link_triggers.values():
                results.add(domain)
        return sorted(list(results))

    @staticmethod
    def latest_for_visit(patient_id, visit_month):
        """Query method to return row matching params

        :param patient_id: User/patient in question
        :param visit_month: integer, zero indexed visit month
        :return: latest trigger state or None if not found
        """
        return TriggerState.query.filter(
            TriggerState.user_id == patient_id).filter(
            TriggerState.visit_month == visit_month).order_by(
            TriggerState.id.desc()).first()

    def resolve_outstanding(self, visit_month):
        """resolve any visits prior to visit_month during transition

        Once the next EMPRO is posted, the window closes for any outstanding
        clinician follow-ups.  Clean up state if any such rows are found
        """
        from .empro_states import EMPRO_state

        # a patient submission closes the window of availability for the
        # post-intervention clinician follow up from any previous visits.
        # mark state if one is found
        outstanding = TriggerState.query.filter(
            TriggerState.user_id == self.user_id).filter(
            TriggerState.state.in_(('triggered', 'resolved'))).filter(
            TriggerState.visit_month < visit_month)
        for row in outstanding:
            dirty = False
            if row.state == 'triggered':
                sm = EMPRO_state(row)
                sm.resolve()
                dirty = True

            if row.triggers.get('action_state') not in (
                    'completed', 'missed', 'not applicable', 'withdrawn'):
                triggers = deepcopy(row.triggers)
                triggers['action_state'] = 'missed'
                row.triggers = triggers
                dirty = True
                current_app.logger.debug(
                    f"persist-trigger_states-change outstanding {row}")
            if dirty:
                db.session.commit()


class TriggerStatesReporting:
    """Manage reporting details for a given patient"""
    MAX_VISIT = 12

    def __init__(self, patient_id):
        self.patient_id = patient_id
        self.latest_by_visit = dict()
        for v in range(self.MAX_VISIT):
            self.latest_by_visit[v] = TriggerState.latest_for_visit(
                patient_id, v)

    def authored_from_visit(self, visit_month):
        """Extract authored datetime from given visit month"""
        if not getattr(
                self.latest_by_visit[visit_month],
                'triggers',
                None):
            return None
        authored = self.latest_by_visit[visit_month].triggers.get(
            "source", {}).get("authored")
        if authored:
            return FHIR_datetime.parse(authored)

    def resolution_authored_from_visit(self, visit_month):
        """Extract resolution authored datetime from given visit month"""
        if not getattr(
                self.latest_by_visit[visit_month],
                'triggers',
                None):
            return None
        resolution_authored = self.latest_by_visit[visit_month].triggers.get(
            "resolution", {}).get("authored")
        if resolution_authored:
            return FHIR_datetime.parse(resolution_authored)

    def resolution_delayed_by_holiday(self, visit_month):
        """Return true if clinician questionnaire response for visit exists with holiday delay

        The clinician has an optional checkbox "Delayed due to local public holiday".  Returns
        true if a questionnaire response for visit exists and such checkbox was set.
        """
        from ..models.questionnaire_response import QuestionnaireResponse
        if not getattr(
                self.latest_by_visit[visit_month],
                'triggers',
                None):
            return None
        qnr_id = self.latest_by_visit[visit_month].triggers.get(
            "resolution", {}).get("qnr_id")
        if not qnr_id:
            return None

        # Pull the clinician's Questionnaire Response, return question answer, if found
        qnr = QuestionnaireResponse.query.get(qnr_id)
        for question_details in qnr.document.get("group", {}).get("question", []):
            # holiday question is: "linkId": "ironman_ss_post_tx.2.1"
            if question_details.get("linkId") == "ironman_ss_post_tx.2.1":
                for answer in question_details.get("answer", []):
                    if "valueBoolean" in answer:
                        return answer["valueBoolean"]

    def domains_accessed(self, visit_month):
        """Return list of domains accessed for visit_month

        :param visit_month: zero indexed month value
        :returns list of EMPRO content domains accessed during the time period
          defined by [EMPRO post date of visit -> post date of next EMPRO],
          or None if n/a

        """
        # Need datetime boundaries for queries
        start_date = self.authored_from_visit(visit_month)
        if not start_date:
            return None

        # user didn't necessarily fill out next.  continue till another
        # submission of EMPRO is found, or default to now()
        visit = visit_month + 1
        end_date = None
        while visit < self.MAX_VISIT:
            end_date = self.authored_from_visit(visit)
            visit += 1
            if end_date:
                break
        if not end_date:
            end_date = datetime.utcnow()

        # Access records are kept in audit table with context 'access'
        hits = Audit.query.filter(
            Audit.subject_id == self.patient_id).filter(
            Audit._context == 'access').filter(
            Audit.timestamp.between(start_date, end_date)).with_entities(
                Audit.comment.distinct())

        if hits.count() == 0:
            return None
        viewed = []
        for path in hits:
            # expected pattern:
            # "remote message: GET /substudy-tailored-content#/pain"
            viewed.append(path[0].split('/')[-1])
        return viewed

    def latest_action_state(self, visit_month):
        """Query method to return row matching params

        :param visit_month: integer, zero indexed visit month
        :return: latest action state or empty string if not found

        """
        ts = self.latest_by_visit[visit_month]
        if not ts or ts.triggers is None:
            return None

        return ts.triggers.get('action_state')

    def hard_triggers_for_visit(self, visit_month):
        """Return list of hard triggers for given visit month

        :param visit_month: zero indexed month value
        :returns list of hard triggers, or None if n/a

        """
        ts = self.latest_by_visit[visit_month]
        if ts:
            return ts.hard_trigger_list()

    def soft_triggers_for_visit(self, visit_month):
        """Return list of soft triggers for given visit month

        :param visit_month: zero indexed month value
        :returns list of soft triggers, or None if n/a

        """
        ts = self.latest_by_visit[visit_month]
        if ts:
            return ts.soft_trigger_list()

    def opted_out_domains_for_visit(self, visit_month):
        """Return list of opted-out domains for given visit month

        :param visit_month: zero indexed month value
        :returns list of domains user opted-out of, or None if n/a

        """
        ts = self.latest_by_visit[visit_month]
        if ts:
            return ts.opted_out_domains()


def rebuild_trigger_states(patient):
    """If a user's consent moves, need to re-build the trigger states for user

    Especially messy process, as much of the data lives in the trigger_states
    table alone, and a consent change may modify start eligibility, etc.
    """
    from .empro_states import initiate_trigger
    from ..models.overall_status import OverallStatus
    from ..models.qb_status import patient_research_study_status
    from ..models.qb_timeline import QBT, update_users_QBT
    from ..models.research_study import BASE_RS_ID, EMPRO_RS_ID
    from ..models.user_consent import consent_withdrawal_dates

    # Use the timeline data for accurate start dates, etc.
    update_users_QBT(user_id=patient.id, research_study_id=EMPRO_RS_ID)
    tl_query = QBT.query.filter(QBT.user_id == patient.id).filter(
        QBT.research_study_id == EMPRO_RS_ID).order_by(QBT.id)
    if not tl_query.count():
        # User has no timeline data for EMPRO, likely not eligible
        if TriggerState.query.filter(TriggerState.user_id == patient.id).count():
            current_app.logging.error(
                f"no EMPRO timeline, yet trigger_states rows for {patient.id}")
        return

    # Capture state in memory for potential reuse when rebuilding
    data = []
    for row in TriggerState.query.filter(
            TriggerState.user_id == patient.id).order_by(TriggerState.id):
        data.append({
            'id': row.id,
            'state': row.state,
            'timestamp': row.timestamp,
            'questionnaire_response_id': row.questionnaire_response_id,
            'triggers': row.triggers,
            'visit_month': row.visit_month,
            })

    if not data:
        # no trigger state data to move, no problem.
        return

    consent_date, wd_date = consent_withdrawal_dates(patient, EMPRO_RS_ID)
    month0_dues = [d for d in data if d.visit_month == 0 and d.state == 'due']
    if len(month0_dues) != 1:
        raise ValueError(f"{patient.id} failed to find trigger_states due row for month 0")
    if (consent_date < month0_dues[0].timestamp) and (
            month0_dues[0].timestamp < consent_date + timedelta(days=30)):
        # if the user's month 0 due is within 30 days of consent, don't shift
        return

    # purge rows and rebuild below
    # TODO TriggerState.delete and rebuild
    current_app.logging.error(
        f"{patient.id} trigger_states out of sync with qb_timeline; requires attention!")
    raise NotImplemented(f"can not adjust trigger_states for {patient.id}")

    if len([c for c in patient.clinicians]) == 0:
        # No valid trigger states without a clinician
        return

    visit_month = -1
    for row in tl_query:
        if row.status == OverallStatus.due:
            # reset any state for next visit:
            visit_month += 1
            conclude_as_expired = False

            # 'due' row starts when they became eligible
            as_of_date = row.at
            study_status = patient_research_study_status(
                patient=patient, as_of_date=as_of_date, skip_initiate=True)

            if study_status[BASE_RS_ID]['ready']:
                # user had unfinished global work at said point in time.
                # check if they complete before the current visit expires
                basestudy_query = QBT.query.filter(QBT.user_id == patient.id).filter(
                    QBT.research_study_id == BASE_RS_ID).filter(
                    QBT.at.between(as_of_date, as_of_date+timedelta(days=30))).filter(
                    QBT.status == OverallStatus.completed).first()
                if basestudy_query:
                    # user finished global work on time, start the visit then
                    as_of_date = basestudy_query.as_of_date
                else:
                    # user was never able to submit visit for given empro month.
                    # stick with initial start date and let it resolve as expired
                    conclude_as_expired = True
            initiate_trigger(patient.id, as_of_date=as_of_date, rebuilding=True)
