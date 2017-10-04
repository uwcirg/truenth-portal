"""Communication model"""
from collections import MutableMapping
from flask import current_app, url_for
import regex
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM

from .assessment_status import AssessmentStatus  # avoid cycle
from .app_text import MailResource
from ..audit import auditable_event
from ..database import db
from ..date_tools import localize_datetime
from ..extensions import user_manager
from .intervention import INTERVENTION
from .message import EmailMessage
from .questionnaire_bank import QuestionnaireBank
from ..trace import dump_trace, establish_trace, trace
from .user import User


# https://www.hl7.org/fhir/valueset-event-status.html
event_status_types = ENUM(
    'preparation', 'in-progress', 'suspended', 'aborted', 'completed',
    'entered-in-error', 'unknown', name='event_statuses',
    create_type=False)


def load_template_args(user, questionnaire_bank_id=None):
    """Capture known variable lookup functions and values

    To add additional template variable lookup functions, name the
    local function with the `_lookup_` prefix to match, i.e::
        `_lookup_first_name` -> `first_name`

    """

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

    def make_button(text):
        inline = False
        if inline:
            match = regex.search(r'href=([^>]+)>([^<]*)', text)
            if not match:
                raise ValueError("Can't make button w/o matching href pattern")

            return (
                '<a href={link} '
                'style="font-size: 0.9em; '
                'font-family: Helvetica, Arial, sans-serif; '
                'display: inline-block; color: #FFF; '
                'background-color: #7C959E; border-color: #7C959E; '
                'border-radius: 0;'
                'letter-spacing: 2px; cursor: pointer; '
                'text-transform: uppercase; text-align: center; '
                'line-height: 1.42857143;'
                'font-weight: 400; padding: 0.6em; text-decoration: none;">'
                '{label}</a>'.format(
                    link=match.groups()[0], label=match.groups()[1]))
        else:
            return text.replace('<a href', '<a class="btn" href')

    def _lookup_assessment_button():
        return make_button(_lookup_assessment_link())

    def _lookup_assessment_link():
        return (
            '<a href="{ae_link}">Assessment Engine</a>'.format(
                ae_link=ae_link()))

    def _lookup_clinic_name():
        org = user.organizations.first()
        if org:
            return org.name
        return ""

    def _lookup_debug_slot():
        """Special slot added when configuration DEBUG_EMAIL is set"""
        open_div = '<div style="background-color: #D3D3D3">'
        close_div = '</div>'

        trace_data = dump_trace()
        if not trace_data:
            trace_data = ['no trace data found']
        result = '{open_div} {trace} {close_div}'.format(
            open_div=open_div, close_div=close_div,
            trace='<br/>'.join(trace_data))
        return result

    def _lookup_first_name():
        name = ''
        if user:
            name = getattr(user, 'first_name', '')
        return name

    def _lookup_last_name():
        name = ''
        if user:
            name = getattr(user, 'last_name', '')
        return name

    def _lookup_parent_org():
        org = user.first_top_organization()
        if org:
            return org.name
        return ""

    def _lookup_password_reset_button():
        return make_button(_lookup_password_reset_link())

    def _lookup_password_reset_link():
        return (
            '<a href="{url}">Password Reset</a>'.format(
                url=url_for('user.forgot_password', _external=True)))

    def _lookup_questionnaire_due_date():
        if not questionnaire_bank_id:
            return ''
        qb = QuestionnaireBank.query.get(questionnaire_bank_id)
        trigger_date = qb.trigger_date(user)
        due = (qb.calculated_overdue(trigger_date) or
               qb.calculated_expiry(trigger_date))
        due_date = localize_datetime(due, user)
        return due_date.strftime('%-d %b %Y') if due_date else ''

    def _lookup_registrationlink():
        return 'url_placeholder'

    def _lookup_st_button():
        return make_button(_lookup_st_link())

    def _lookup_st_link():
        return '<a href="{0.link_url}">Symptom Tracker</a>'.format(
            INTERVENTION.SELF_MANAGEMENT)

    def _lookup_verify_account_button():
        return make_button(_lookup_verify_account_link())

    def _lookup_verify_account_link():
        token = user_manager.token_manager.generate_token(user.id)
        url = url_for(
            'portal.access_via_token', token=token, _external=True)
        system_user = User.query.filter_by(email='__system__').one()
        auditable_event(
            "generated access token for user {} to embed in email".format(
                user.id),
            user_id=system_user.id, subject_id=user.id,
            context='authentication')
        return '<a href="{url}">Verify Account</a>'.format(url=url)

    # Load all functions from the local space with the `_lookup_` prefix
    # into the args instance
    args = DynamicDictLookup()
    for fname, function in locals().items():
        if fname.startswith('_lookup_'):
            # chop the prefix and assign to the function
            args[fname[len('_lookup_'):]] = function
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
        if not self.communication_request:
            from .communication_request import CommunicationRequest
            self.communication_request = CommunicationRequest.query.get(
                self.communication_request_id)
        return (
            'Communication for user {0.user_id}'
            ' of {0.communication_request.name}'.format(self))

    def generate_and_send(self):
        "Collate message details and send"

        if current_app.config.get('DEBUG_EMAIL', False):
            # hack to restart trace when in loop from celery task
            # don't want to reset if in the middle of a request
            from celery import current_task
            establish_trace(
                "BEGIN trace as per DEBUG_EMAIL configuration",
                reset_trace=current_task is None)

        user = User.query.get(self.user_id)
        if not user.email or '@' not in user.email:
            raise ValueError(
                "can't send communication to user w/o valid email address")

        trace("load variables for {user} & UUID {uuid} on {request}".format(
            user=user,
            uuid=self.communication_request.lr_uuid,
            request=self.communication_request.name))
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
