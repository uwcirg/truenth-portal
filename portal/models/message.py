"""Model classes for message data"""
from datetime import datetime
from flask import current_app
from flask_mail import Message
from flask_mail import email_dispatched

from ..extensions import db, mail


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
    sent_at = db.Column(db.DateTime, default=datetime.now)
    body = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id',
        ondelete='CASCADE'))

    def send_message(self):
        message = Message(subject=self.subject,
                sender=current_app.config['DEFAULT_MAIL_SENDER'],
                recipients=self.recipients.split())
        message.html = self.body
        mail.send(message)
