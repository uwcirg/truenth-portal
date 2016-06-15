"""Group module

Groups are intented to cluster users together for logical reasons,
such as a list of users for whom patient notifications apply.  Groups
should not be used to grant or restrict access - see `Role`.

"""
from sqlalchemy import UniqueConstraint
from ..extensions import db


class Group(db.Model):
    """SQLAlchemy class for `groups` table"""
    __tablename__ = 'groups'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(50), unique=True)
    description = db.Column(db.Text)

    def __str__(self):
        return "Group {}".format(self.name)


class UserGroup(db.Model):
    __tablename__ = 'user_groups'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id',
        ondelete='CASCADE'), nullable=False)
    group_id = db.Column(db.Integer(), db.ForeignKey('groups.id',
        ondelete='CASCADE'), nullable=False)

    __table_args__ = (UniqueConstraint('user_id', 'group_id',
        name='_user_group'),)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "UserGroup {0.user_id}:{0.group_id}".format(self)
