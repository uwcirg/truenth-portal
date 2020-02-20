"""User Preference module"""
import enum
from sqlalchemy import Enum, UniqueConstraint

from ..database import db


class PreferenceTypes(enum.Enum):
    suppress_email = 1


class UserPreference(db.Model):
    """Captures user preferences such as suppress_email_communication"""
    __tablename__ = 'user_preferences'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    preference_name = db.Column(Enum(PreferenceTypes), nullable=False)

    __table_args__ = (UniqueConstraint(
        'user_id', 'preference_name', name='_user_preference_uniq'),)

    def __str__(self):
        return (
            "UserPreference({0.user_id}, {0.preference_name})".format(self))
