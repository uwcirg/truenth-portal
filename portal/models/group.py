"""Group module

Groups are intented to cluster users together for logical reasons,
such as a list of users for whom patient notifications apply.

Groups should not be used to grant or restrict access - see `Role`.

"""
import re

from sqlalchemy import UniqueConstraint
from werkzeug.exceptions import BadRequest

from ..database import db


class Group(db.Model):
    """SQLAlchemy class for `groups` table"""
    __tablename__ = 'groups'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(50), unique=True)
    description = db.Column(db.Text)

    def __str__(self):
        return "Group {}".format(self.name)

    def as_json(self):
        return {'name': self.name, 'description': self.description}

    @classmethod
    def from_json(cls, data):
        instance = cls()
        instance.name = cls.validate_name(data['name'])
        instance.description = data['description']
        return instance

    @staticmethod
    def validate_name(name):
        """Only accept lowercase letters and underscores in name

        :returns: the name if valid
        :raises BadRequest: on error

        """
        if re.match(r'^[a-z][a-z0-9_]*$', name):
            return name
        raise BadRequest(
            "Group name may only contain lowercase letters and underscores")


class UserGroup(db.Model):
    __tablename__ = 'user_groups'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(
        db.Integer(), db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False)
    group_id = db.Column(
        db.Integer(), db.ForeignKey('groups.id', ondelete='CASCADE'),
        nullable=False)

    __table_args__ = (UniqueConstraint(
        'user_id', 'group_id', name='_user_group'),)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "UserGroup {0.user_id}:{0.group_id}".format(self)
