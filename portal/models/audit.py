"""Audit Module"""
from datetime import datetime
from enum import Enum

from dateutil import parser
from flask import current_app

from ..database import db
from .reference import Reference


def lookup_version():
    return current_app.config.metadata['version']


class Context(Enum):
    # only add new contexts to END of list, otherwise ordering gets messed up
    (other, login, assessment, authentication, intervention, account,
     consent, user, observation, organization, group, procedure,
     relationship, role, tou, access) = range(16)


class Audit(db.Model):
    """ORM class for audit data

    Holds meta info about changes in other tables, such as when and
    by whom the data was added.  Several other tables maintain foreign
    keys to audit rows, such as `Observation` and `Procedure`.

    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    _context = db.Column('context', db.Text, default='other', nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    version = db.Column(db.Text, default=lookup_version, nullable=False)
    comment = db.Column(db.Text)

    def __str__(self):
        return (
            "Audit by user {0.user_id} on user {0.subject_id} at "
            "{0.timestamp}: {0.context}: {0.comment}".format(self))

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, ct_string):
        self._context = getattr(Context, ct_string).name

    def as_fhir(self):
        """Typically included as *meta* data in containing FHIR resource"""
        from .user import User
        from .fhir import FHIR_datetime

        d = {}
        d['version'] = self.version
        d['lastUpdated'] = FHIR_datetime.as_fhir(self.timestamp)
        d['by'] = Reference.patient(self.user_id).as_fhir()
        d['by']['display'] = User.query.get(self.user_id).display_name
        d['on'] = Reference.patient(self.subject_id).as_fhir()
        d['context'] = self.context
        if self.comment:
            d['comment'] = self.comment
        return d

    @classmethod
    def from_logentry(cls, entry):
        """Parse and create an Audit instance from audit log entry

        Prior to version v16.5.12, audit entries only landed in log.
        This may be used to convert old entries, but newer ones should
        already be there.

        """

        # 2016-02-23 10:07:05,953: performed by 10033 on 10033: login: logout
        fields = entry.split(':')
        dt = parser.parse(':'.join(fields[0:2]))
        user_id = int(fields[3].split()[2])
        subject_id = int(fields[3].split()[4])
        context = fields[4].strip()
        message = ':'.join(fields[5:])
        return cls(
            user_id=user_id, subject_id=subject_id, context=context,
            timestamp=dt, comment=message)
