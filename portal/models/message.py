"""Model classes for message data"""
from datetime import datetime
from textwrap import fill
from flask import current_app
from flask_mail import Message
from flask_mail import email_dispatched

from ..audit import auditable_event
from ..database import db
from ..extensions import mail
from .user import User


def log_message(message, app):
    """Configured to handle signals on email_dispatched - log the event"""
    app.logger.info(u"Message sent; To: {0} Subj: {1}".format(
        message.recipients, message.subject))


email_dispatched.connect(log_message)


EMAIL_HEADER = (
    u"<!DOCTYPE html>"
    "<html><head><title>TrueNTH email</title><style>"
    "body {"
    " font-size: 16px;"
    "}"
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
    "</style></head><body>")
EMAIL_FOOTER = u"</body></html>"


class EmailMessage(db.Model):
    __tablename__ = 'email_messages'
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(255), nullable=False)
    recipients = db.Column(db.Text, nullable=False)
    sender = db.Column(db.String(255), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    body = db.Column(db.Text, nullable=False)
    # nullable as anonymous support requests won't have associated users
    user_id = db.Column(
        db.Integer(), db.ForeignKey('users.id', ondelete='CASCADE'))

    def style_message(self, body):
        """Implicitly called on send, to wrap body with style tags"""
        # Catch duplicate styling attempts
        restricted = (u'doctype', u'html', u'head', u'body')
        lower_body = body.lower()
        for element in restricted:
            if element in lower_body:
                raise ValueError(
                    "Unexpected element '{}' found in email body".format(
                        element))
        return u'{header}{body}{footer}'.format(
            header=EMAIL_HEADER, body=body, footer=EMAIL_FOOTER)

    def send_message(self):
        message = Message(
            subject=self.subject,
            sender=current_app.config['DEFAULT_MAIL_SENDER'],
            recipients=self.recipients.split())
        body = self.style_message(self.body)
        message.html = fill(body, width=280)
        mail.send(message)

        user = User.query.filter_by(email='__system__').first()
        user_id = user.id if user else None
        recipient = self.recipients.split()[0]
        subject = User.query.filter_by(email=recipient).first()
        subject_id = subject.id if subject else self.user_id

        if user_id and subject_id:
            audit_msg = ("EmailMessage '{0.subject}' sent to "
                         "{0.recipients} from {0.sender}".format(self))
            auditable_event(message=audit_msg, user_id=user_id,
                            subject_id=subject_id, context="user")

    def __str__(self):
        return "EmailMessage subj:{} sent_at:{}".format(self.subject,
                                                        self.sent_at)
