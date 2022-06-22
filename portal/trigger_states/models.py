from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import make_transient

from ..database import db
from ..date_tools import FHIR_datetime, weekday_delta
from ..models.audit import Audit

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


class TriggerStatesReporting:
    """Manage reporting details for a given patient"""
    MAX_VISIT = 12

    def __init__(self, patient_id):
        self.patient_id = patient_id
        self.latest_by_visit = dict()
        for v in range(self.MAX_VISIT):
            self.latest_by_visit[v] = TriggerState.latest_for_visit(
                patient_id, v)

    def domains_accessed(self, visit_month):
        """Return list of domains accessed for visit_month

        :param visit_month: zero indexed month value
        :returns list of EMPRO content domains accessed during the time period
          defined by [EMPRO post date of visit -> post date of next EMPRO],
          or None if n/a

        """
        def authored_from_visit(visit_month):
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

        # Need datetime boundaries for queries
        start_date = authored_from_visit(visit_month)
        if not start_date:
            return None

        # user didn't necessarily fill out next.  continue till another
        # submission of EMPRO is found, or default to now()
        visit = visit_month + 1
        while visit < self.MAX_VISIT:
            end_date = authored_from_visit(visit)
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

        return ts.triggers['action_state']

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
