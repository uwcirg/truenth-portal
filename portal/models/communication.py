"""Communication model"""
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM

from ..database import db


# https://www.hl7.org/fhir/valueset-event-status.html
event_status_types = ENUM(
    'preparation', 'in-progress', 'suspended', 'aborted', 'completed',
    'entered-in-error', 'unknown', name='event_statuses',
    create_type=False)


class Communication(db.Model):
    """Model representing a FHIR-like Communication Resource

    Used to track communications tied to a user `basedOn` a
    CommunicationRequest.

    """
    __tablename__ = 'communications'
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column('status', event_status_types, nullable=False)

    # FHIR Communication spec says `basedOn` can retur to any
    # object.  For current needs, this is always a CommunicationRequest
    communication_request_id = db.Column(
        db.ForeignKey('communication_requests.id'), nullable=False)
    communication_request = db.relationship('CommunicationRequest')

    user_id = db.Column(db.ForeignKey(
        'users.id', ondelete='cascade'), nullable=False)

    # message_id is null until sent
    message_id = db.Column(db.ForeignKey(
        'email_messages.id', ondelete='cascade'), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            communication_request_id, user_id,
            name='_communication_request_user'),
    )

    def __str__(self):
        return (
            'Communication for {0.user_id}'
            ' of {0.communication_request_id}'.format(self))
