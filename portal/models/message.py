"""Model classes for message data"""

from datetime import datetime
from flask import current_app
from smtplib import SMTPRecipientsRefused
from sqlalchemy.ext.hybrid import hybrid_property
from textwrap import fill

from flask_mail import Message, email_dispatched

from .app_text import MailResource, app_text
from ..audit import auditable_event
from ..database import db
from ..extensions import mail
from .organization import OrgTree
from .user import INVITE_PREFIX, User, patients_query


def log_message(message, app):
    """Configured to handle signals on email_dispatched - log the event"""
    app.logger.info("Message sent; To: {0} Subj: {1}".format(
        message.recipients, message.subject))


email_dispatched.connect(log_message)

EMAIL_HEADER = (
    "<!DOCTYPE html><html>"
    "<head><title>TrueNTH email</title><style>"
    "body {"
    " font-size: 16px;"
    "} "
    "table, th, td {"
    " border: 1px solid #ddd;"
    "} "
    "table { "
    " border-collapse: collapse;"
    " border-spacing: 0;"
    " display: table;"
    "} "
    "th { "
    " color: #FFF;"
    " background-color: #8a8e90;"
    " padding: 8px;"
    " font-weight: 400;"
    " border-left: 1px solid #ddd;"
    " margin: 0;"
    " display: table-cell;"
    "} "
    "tr { "
    " display: table-row;"
    "} "
    "td { "
    " padding: 8px;"
    " display: table-cell;"
    "} "
    " .btn {"
    " font-size: 0.9em;"
    " font-family: Helvetica, Arial, sans-serif;"
    " display: inline-block;"
    " color: #FFF;"
    " background-color: #7C959E;"
    " border-color: #7C959E;"
    " border-radius: 0;"
    " letter-spacing: 2px;"
    " cursor: pointer;"
    " text-transform: uppercase;"
    " text-align: center;"
    " line-height: 1.42857143;"
    " font-weight: 400;"
    " padding: 0.6em;"
    " text-decoration: none;"
    "}"
    " .btn:hover {"
    " background-color: #576e76;"
    "}"
    " .btn a {"
    " color: #FFF;"
    " text-decoration: none;"
    "}"
    "</style></head><body>")
EMAIL_FOOTER = "</body></html>"


def extra_headers():
    """Function to deliver any configured extra_headers for outbound email

    Returns an empty dict, or one including any desired extra_headers, such
    as a ``List-Unsubscribe`` header.

    """
    # TN-2386 Include List-Unsubscribe header to improve spam scores
    return {'List-Unsubscribe': "<mailto:{}?subject=unsubscribe>".format(
        current_app.config['CONTACT_SENDTO_EMAIL'])}


class EmailMessage(db.Model):
    __tablename__ = 'email_messages'
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(255), nullable=False)
    _recipients = db.Column("recipients", db.Text, index=True, nullable=False)
    sender = db.Column(db.String(255), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    body = db.Column(db.Text, nullable=False)
    # nullable as anonymous support requests won't have associated users
    user_id = db.Column(
        db.Integer(), db.ForeignKey('users.id', ondelete='CASCADE'))
    recipient_id = db.Column(
        db.Integer(), db.ForeignKey('users.id', ondelete='CASCADE'))

    @hybrid_property
    def recipients(self):
        return self._recipients

    @recipients.setter
    def recipients(self, value):
        """Set recipients_id if a user is found w/ matching email"""

        if value is None:
            self._recipients = None
            self.recipient_id = None
            return

        # As the schema only tracks a single recipient_id, capture abuse;
        # don't allow comma in recipients till schema can capture
        if ',' in value:
            raise ValueError("schema only supports single recipient")

        recipient_user = User.query.filter_by(email=value).first()
        if not recipient_user:
            # Capture email sent to a user prior to registration
            recipient_user = User.query.filter_by(email="{}{}".format(
                INVITE_PREFIX, value)).first()
        if recipient_user:
            self.recipient_id = recipient_user.id
        self._recipients = value

    @staticmethod
    def style_message(body):
        """Implicitly called on send, to wrap body with style tags"""
        # Catch duplicate styling attempts
        restricted = ('<!doctype', '<html', '<head', '<body')
        lower_body = body.lower()
        for element in restricted:
            if element in lower_body:
                raise ValueError(
                    "Unexpected element '{}' found in email body".format(
                        element))
        return '{header}{body}{footer}'.format(
            header=EMAIL_HEADER, body=body, footer=EMAIL_FOOTER)

    def send_message(self, cc_address=None):
        """Send the message

        :param cc_address: include valid email address to send a carbon copy

        NB the cc isn't persisted with the rest of the record.

        """
        if not self.recipients:
            current_app.logger.error(
                "can't email w/o recipients.  failed to send "
                f"'{self.subject}' to user {self.recipient_id}")
        message = Message(
            subject=self.subject,
            extra_headers=extra_headers(),
            recipients=self.recipients.split())
        if cc_address:
            message.cc.append(cc_address)
        body = self.style_message(self.body)
        message.html = fill(
            body, width=280, break_long_words=False, break_on_hyphens=False)
        exc = None
        try:
            current_app.logger.debug(f"sending message {self.subject}")
            mail.send(message)
            current_app.logger.debug(f"sent message {self.subject}")
        except Exception as e:
            current_app.logger.debug(f"exception sending message: {e}")
            exc = e

        user = User.query.filter_by(email='__system__').first()
        user_id = user.id if user else None
        recipient = self.recipients.split()[0]
        subject = User.find_by_email(recipient)
        subject_id = subject.id if subject else self.user_id

        if user_id and subject_id:
            audit_msg = ("EmailMessage '{0.subject}' sent to "
                         "{0.recipients} from {0.sender}".format(self))
            if exc:
                audit_msg = "ERROR {}; {}".format(str(exc), audit_msg)
            auditable_event(message=audit_msg, user_id=user_id,
                            subject_id=subject_id, context="user")
        else:
            # This should never happen, alert if it does
            current_app.logger.error(
                "Unable to generate audit log for email to %s: %s",
                recipient, str(message))
        # If an exception was raised when attempting the send, re-raise now
        # for clients to manage
        if exc:
            raise exc

    def __str__(self):
        return "EmailMessage subj:{} sent_at:{}".format(
            self.subject, self.sent_at)

    def as_json(self):
        d = {
            'id': self.id, 'sender': self.sender,
            'recipients': self.recipients, 'subject': self.subject,
            'body': self.body, 'sent_at': self.sent_at,
            'user_id': self.user_id}
        return d


class Newsletter(object):
    """Manages compiling newsletter content and sending out.
    """

    def __init__(self, org_id, research_study_id, content_key):
        self.org_id = org_id
        self.research_study_id = research_study_id
        self.content_key = content_key

    def transmit(self):
        acting_user = User.query.filter_by(email='__system__').one()
        resource_url = app_text(self.content_key)
        requested_orgs = (
            OrgTree().here_and_below_id(organization_id=self.org_id) if self.org_id
            else None)
        error_emails = []
        for patient in patients_query(
                acting_user=acting_user,
                research_study_id=self.research_study_id,
                requested_orgs=requested_orgs):
            if not patient.email_ready()[0]:
                continue
            item = MailResource(resource_url, patient.locale_code)
            msg = EmailMessage(
                subject=item.subject,
                body=item.body,
                recipients=patient.email,
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                user_id=acting_user.id,
                recipient_id=patient.id)
            try:
                msg.send_message()
            except SMTPRecipientsRefused as exc:
                current_app.logger.error(
                    f"Error sending %s to %s: %s",
                    self.content_key, patient.email, exc)
                error_emails.append(patient.email)
            db.session.add(msg)

        db.session.commit()
        return error_emails
