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
    app.logger.info(u"Message sent; To: {0} Subj: {1}".\
            format(message.recipients, message.subject))


email_dispatched.connect(log_message)


class EmailMessage(db.Model):
    __tablename__ = 'email_messages'
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(255), nullable=False)
    recipients = db.Column(db.Text, nullable=False)
    sender = db.Column(db.String(255), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    body = db.Column(db.Text, nullable=False)
    # nullable as anonymous support requests won't have associated users
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id',
        ondelete='CASCADE'))

    def send_message(self):
        message = Message(subject=self.subject,
                sender=current_app.config['DEFAULT_MAIL_SENDER'],
                recipients=self.recipients.split())
        message.html = fill(self.body, width=280)
        mail.send(message)

        user = User.query.filter_by(email=self.sender).first()
        user_id = user.id if user else self.user_id
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
