"""Audit Module"""
from datetime import datetime
from dateutil import parser
from flask import current_app

from ..extensions import db
from .fhir import FHIR_datetime
from .reference import Reference


def lookup_version():
    return current_app.config.metadata.version


class Audit(db.Model):
    """ORM class for audit data

    Holds meta info about changes in other tables, such as when and
    by whom the data was added.  Several other tables maintain foreign
    keys to audit rows, such as `Observation` and `Procedure`.

    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    version = db.Column(db.Text, default=lookup_version, nullable=False)
    comment = db.Column(db.Text)

    def __str__(self):
        return "Audit user {0.user_id} at {0.timestamp} {0.comment}".\
                format(self)

    def as_fhir(self):
        """Typically included as *meta* data in containing FHIR resource"""
        d = {}
        d['version'] = self.version
        d['lastUpdated'] = FHIR_datetime.as_fhir(self.timestamp)
        d['by'] = Reference.patient(self.user_id).as_fhir()
        return d

    @classmethod
    def from_logentry(cls, entry):
        """Parse and create an Audit instance from audit log entry

        Prior to version v16.5.12, audit entries only landed in log.
        This may be used to convert old entries, but newer ones should
        already be there.

        """

        #2016-02-23 10:07:05,953: 10033 performed: logout
        fields = entry.split(':')
        dt = parser.parse(':'.join(fields[0:2]))
        user_id = int(fields[3].split()[0])
        message = ':'.join(fields[4:])
        return cls(user_id=user_id, timestamp=dt, comment=message)
