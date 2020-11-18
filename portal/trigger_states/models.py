from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import make_transient

from ..database import db
from ..date_tools import FHIR_datetime


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
    NB only rows with `state` = `processed` include triggers.

    """
    __tablename__ = 'trigger_states'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False, index=True)
    state = db.Column('state', trigger_state_enum, nullable=False, index=True)
    timestamp = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    questionnaire_response_id = db.Column(
        db.ForeignKey('questionnaire_responses.id'), index=True)
    triggers = db.Column(JSONB)

    def as_json(self):
        results = {'state': self.state, 'user_id': self.user_id}
        if self.timestamp:
            results['timestamp'] = FHIR_datetime.as_fhir(self.timestamp)
        if self.triggers:
            results['triggers'] = self.triggers
        return results

    def __repr__(self):
        return (
            "TriggerState on user {0.user_id}: {0.state}".format(self))

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
        return results

    def reminder_due(self):
        """Determine if reminder is due from internal state"""
        first_sent = FHIR_datetime.parse(
            self.triggers['actions']['email'][0]['timestamp'])
        last_sent = FHIR_datetime.parse(
            self.triggers['actions']['email'][-1]['timestamp'])
        now = datetime.utcnow()

        # To be sent daily after the initial 48 hours
        needed_delta = timedelta(days=1)
        if first_sent + timedelta(hours=1) > last_sent:
            # only initial has been sent.  need 48 hours to have passed
            needed_delta = timedelta(days=2)

        return now > last_sent + needed_delta

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
        return list(results)
