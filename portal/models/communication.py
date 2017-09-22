"""Communication model"""
from collections import MutableMapping
from flask import current_app, url_for
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM

from .assessment_status import AssessmentStatus  # avoid cycle
from .app_text import MailResource
from ..database import db
from .intervention import INTERVENTION
from .message import EmailMessage
from .questionnaire_bank import QuestionnaireBank
from .user import User


# https://www.hl7.org/fhir/valueset-event-status.html
event_status_types = ENUM(
    'preparation', 'in-progress', 'suspended', 'aborted', 'completed',
    'entered-in-error', 'unknown', name='event_statuses',
    create_type=False)


def load_template_args(user, questionnaire_bank_id):
    """Capture known variable lookup functions and values"""

    def ae_link():
        assessment_status = AssessmentStatus(user=user)
        link_url = url_for(
            'assessment_engine_api.present_assessment',
            instrument_id=assessment_status.
            instruments_needing_full_assessment(classification='all'),
            resume_instrument_id=assessment_status.
            instruments_in_progress(classification='all'),
            _external=True)
        return link_url

    def assessment_button():
        return (
            '<div class="btn"><a href="{ae_link}">'
            'Assessment Button</a></div>'.format(ae_link=ae_link()))

    def assessment_link():
        return (
            '<a href="{ae_link}">Assessment Link</a>'.format(
                ae_link=ae_link()))

    def clinic_name():
        org = user.organizations.first()
        if org:
            return org.name
        return ""

    def parent_org():
        org = user.first_top_organization()
        if org:
            return org.name
        return ""

    def questionnaire_due_date():
        qb = QuestionnaireBank.query.get(questionnaire_bank_id)
        trigger_date = qb.trigger_date(user)
        due = (qb.calculated_overdue(trigger_date) or
               qb.calculated_expiry(trigger_date))
        return due.strftime('%-d %b %Y') if due else ''

    def st_link():
        return '<a href="{0.link_url}">Symptom Tracker</a>'.format(
            INTERVENTION.SELF_MANAGEMENT)

    args = DynamicDictLookup()
    args['assessment_button'] = assessment_button
    args['assessment_link'] = assessment_link
    args['clinic_name'] = clinic_name
    args['first_name'] = user.first_name
    args['last_name'] = user.last_name
    args['parent_org'] = parent_org
    args['questionnaire_due_date'] = questionnaire_due_date
    args['st_link'] = st_link
    return args


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
    message = db.relationship('EmailMessage')

    __table_args__ = (
        UniqueConstraint(
            communication_request_id, user_id,
            name='_communication_request_user'),
    )

    def __str__(self):
        return (
            'Communication for {0.user_id}'
            ' of {0.communication_request_id}'.format(self))

    def generate_and_send(self):
        "Collate message details and send"
        user = User.query.get(self.user_id)
        args = load_template_args(
            user=user,
            questionnaire_bank_id=self.communication_request.
            questionnaire_bank_id)

        mailresource = MailResource(
            url=self.communication_request.content_url,
            variables=args)

        missing = set(mailresource.variable_list) - set(args)
        if missing:
            raise ValueError(
                "{} contains unknown varables: {}".format(
                    self.communication_request.content_url,
                    ','.join(missing)))
        self.message = EmailMessage(
            subject=mailresource.subject,
            body=mailresource.body,
            recipients=user.email,
            sender=current_app.config['DEFAULT_MAIL_SENDER'],
            user_id=user.id)
        self.message.send_message()
        self.status = 'completed'


class DynamicDictLookup(MutableMapping):
    """Dictionary like interface with lazy lookup of values"""

    def __init__(self, *args, **kwargs):
        self.store = dict()
        self.update(dict(*args, **kwargs))

    def __getitem__(self, key):
        if key in self.store:
            value = self.store[key]
            if callable(value):
                return self.store[key].__call__()
            return value
        else:
            raise KeyError(key)

    def __setitem__(self, key, value):
        self.store[key] = value

    def __delitem__(self, key):
        del self.store[key]

    def __len__(self):
        return len(self.store)

    def __iter__(self):
        return iter(self.store)
