"""User Notification module"""
from datetime import datetime
from sqlalchemy import UniqueConstraint

from ..database import db
from ..date_tools import FHIR_datetime


class Notification(db.Model):
    """Notification model for storing general dashboard notifications

    """
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow)

    def __str__(self):
        return "Notification {0.id} with content {0.content}".format(self)

    @classmethod
    def from_json(cls, data):
        for field in ('name', 'content'):
            if field not in data:
                raise ValueError("missing required {} field".format(field))
        instance = cls()
        return instance.update_from_json(data)

    def update_from_json(self, data):
        self.name = data['name']
        self.content = data['content']
        if 'created_at' in data:
            self.created_at = data['created_at']
        return self

    def as_json(self):
        d = {}
        d['id'] = self.id
        d['resourceType'] = 'Notification'
        d['name'] = self.name
        d['content'] = self.content
        d['created_at'] = FHIR_datetime.as_fhir(self.created_at)
        return d


class UserNotification(db.Model):
    """UserNotification model for storing a user's Notifications

    Tracks Notifications to be shown on the user's dashboard.
    Delete Notifications from a user's UserNotifications to stop them from
    being shown to that user.
    """
    __tablename__ = 'user_notifications'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(
        db.Integer(),
        db.ForeignKey(
            'users.id',
            ondelete='CASCADE'),
        nullable=False)
    notification_id = db.Column(
        db.Integer(),
        db.ForeignKey(
            'notifications.id',
            ondelete='CASCADE'),
        nullable=False)

    __table_args__ = (UniqueConstraint('user_id', 'notification_id',
                                       name='_user_notification'),)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "UserNotification {0.user_id}:{0.notification_id}".format(self)
