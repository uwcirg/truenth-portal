"""CommunicationRequest model"""
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM

from .communication import Communication
from ..database import db
from .identifier import Identifier
from .message import EmailMessage
from .reference import Reference


# https://www.hl7.org/fhir/valueset-request-status.html
request_status_types = ENUM(
    'draft', 'active', 'suspended', 'cancelled', 'completed',
    'entered-in-error', 'unknown', name='request_statuses',
    create_type=False)


class CommunicationRequest(db.Model):
    """Model representing a FHIR-like CommunicationRequest

    CommunicationRequest is used to capture business rules surrounding
    messages, reminders and other forms of communications.

    As the base event which defines the time often moves due to
    procedures and diagnosis, time deltas are generally persisted
    within the CommunicationRequest rather than a static datetime.

    CommunicationRequests are associated with a set of users by a
    QuestionnaireBank, such that for any user for whom the
    QuestionnaireBank applies, send the communication (unless
    the QuestionnaireBank is completed or expired).

    NB - several exceptions from the FHIR spec exist for this model,
    as the FHIR doesn't well handle time deltas and associations as needed.

    """
    __tablename__ = 'communication_requests'
    id = db.Column(db.Integer, primary_key=True)
    identifiers = db.relationship(
        'Identifier', lazy='dynamic',
        secondary="communication_request_identifiers")
    status = db.Column('status', request_status_types, nullable=False)
    notify_days_after_event = db.Column(db.Integer, nullable=False)

    questionnaire_bank_id = db.Column(
        db.ForeignKey('questionnaire_banks.id'), nullable=False)
    questionnaire_bank = db.relationship('QuestionnaireBank')

    __table_args__ = (
        UniqueConstraint(
            questionnaire_bank_id, notify_days_after_event,
            name='_communication_request_qb_days'),
    )

    def __str__(self):
        return (
            'CommunicationRequest for {0.questionnaire_bank}'
            ' on {0.notify_days_after_event}'.format(self))

    @classmethod
    def from_fhir(cls, data):
        instance = cls()
        return instance.update_from_fhir(data)

    def update_from_fhir(self, data):
        self.status = data['status']
        self.notify_days_after_event = data['notify_days_after_event']
        if 'identifier' in data:
            for id in data['identifier']:
                identifier = Identifier.from_fhir(id).add_if_not_found()
                if identifier not in self.identifiers.all():
                    self.identifiers.append(identifier)
        self.questionnaire_bank_id = Reference.parse(
            data['questionnaire_bank']).id
        self = self.add_if_not_found(commit_immediately=True)
        return self

    def as_fhir(self):
        d = {}
        d['resourceType'] = 'CommunicationRequest'
        d['status'] = self.status
        d['notify_days_after_event'] = self.notify_days_after_event
        d['questionnaire_bank'] = Reference.questionnaire_bank(
            self.questionnaire_bank_id).as_fhir()
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, adds new if not found.

        @return: the new or matched CommunicationRequest

        """
        existing = CommunicationRequest.query.filter(
            CommunicationRequest.questionnaire_bank_id ==
            self.questionnaire_bank_id).filter(
                CommunicationRequest.notify_days_after_event ==
                self.notify_days_after_event).first()
        if not existing:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        else:
            self.id = existing.id
        self = db.session.merge(self)
        return self


class CommunicationRequestIdentifier(db.Model):
    """link table for CommunicationRequest : n identifiers"""
    __tablename__ = 'communication_request_identifiers'
    id = db.Column(db.Integer, primary_key=True)
    communication_request_id = db.Column(db.ForeignKey(
        'communication_requests.id', ondelete='cascade'), nullable=False)
    identifier_id = db.Column(db.ForeignKey(
        'identifiers.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint(
        'communication_request_id', 'identifier_id',
        name='_communication_request_identifier'),)


def trigger_communications():
    """Lookup and trigger any outstanding communications"""

    def completed_communication(user_id, communication_request_id):
        "Return a matching completed communication, if found"
        # if this request has been sent, move on
        sent = Communication.query.filter(
            Communication.user_id == user_id
        ).filter(
            Communication.communication_request_id == communication_request_id
        ).filter(
            Communication.status == 'completed').first()
        return sent

    def pending_questionnaire_bank(user_id, questionnaire_bank):
        """Return True if oustanding work in valid time remains

        Users may have completed all the related questionnaires, or they may
        have failed to do so prior to valid time allowed for each.

        :returns: True IFF there is remaining work for the user to complete at
        this time

        """
        # Waiting on refactor of assessment status to take a QB
        raise NotImplementedError("finish me")

    def generate_communication(user, communication_request):
        # Fabricate an email_message and send

        communication = Communication(
            user_id=user.id,
            status='preparation',
            communication_request_id=communication_request.id)
        db.session.add(communication)
        subject = communication_request.subject
        body = communication_request.body
        recipients = user.email

        email = EmailMessage(
            subject=subject, body=body,
            recipients=recipients, sender=user.email,
            user_id=user.id)
        db.session.add(email)
        email.send_message()
        communication.message = email
        communication.status = 'completed'
        db.session.commit()

    for request in CommunicationRequest.query.filter(
            CommunicationRequest.status == 'active'):
        # Complex task, to determine if a communication
        # should be sent.  We only send if the user qualifies,
        # namely the user hasn't already been sent a matching
        # communication and hasn't fulfilled the point of the
        # communication (such as having completed a questionnaire
        # for which this communication is reminding them to do)

        for user in request.questionnaire_bank.eligible_users():
            # Continue if matching messages already sent
            if completed_communication(
                    user_id=user.id,
                    communication_request_id=request.id):
                continue

            # Confirm reason for message remains
            if pending_questionnaire_bank(
                    user=user,
                    questionnaire_bank=request.questionnaire_bank):

                generate_communication(
                    user=user,
                    communication_request=request)
