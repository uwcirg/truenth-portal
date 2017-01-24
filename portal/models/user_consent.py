"""User Consent module"""
from datetime import datetime, timedelta
from sqlalchemy.ext.hybrid import hybrid_property
from validators import url as url_validation

from .audit import Audit
from ..extensions import db
from .fhir import FHIR_datetime
from .organization import Organization
from .user import User

def default_expires():
    """5 year from now, in UTC"""
    return datetime.utcnow() + timedelta(days=365*5)


STAFF_EDITABLE_MASK = 0b001
INCLUDE_IN_REPORTS_MASK = 0b010
SEND_REMINDERS_MASK = 0b100


class UserConsent(db.Model):
    """ORM class for user_consent data

    Capture data when user consents to share data with an organization.

    """
    __tablename__ = 'user_consents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    organization_id = db.Column(
        db.ForeignKey('organizations.id'), nullable=False)
    audit_id = db.Column(db.ForeignKey('audit.id'), nullable=False)
    deleted_id = db.Column(db.ForeignKey('audit.id'), nullable=True)
    expires = db.Column(db.DateTime, default=default_expires, nullable=False)
    agreement_url = db.Column(db.Text, nullable=False)
    options = db.Column(db.Integer, nullable=False, default=0)

    audit = db.relationship(Audit, cascade="save-update",
                            foreign_keys=[audit_id])
    deleted = db.relationship(Audit, cascade="save-update",
                              foreign_keys=[deleted_id])
    organization = db.relationship(Organization, cascade="save-update")

    def __init__(self, **kwargs):
        self.options = 0
        super(UserConsent, self).__init__(**kwargs)

    def __str__(self):
        return ("user_consent at {0.agreement_url} between {0.user_id} and "
                "{0.organization_id}".format(self))

    @hybrid_property
    def staff_editable(self):
        return self.options & STAFF_EDITABLE_MASK

    @staff_editable.setter
    def staff_editable(self, value):
        if value:
            self.options = self.options | STAFF_EDITABLE_MASK
        else:
            self.options = self.options & ~STAFF_EDITABLE_MASK

    @hybrid_property
    def include_in_reports(self):
        return self.options & INCLUDE_IN_REPORTS_MASK

    @include_in_reports.setter
    def include_in_reports(self, value):
        if value:
            self.options = self.options | INCLUDE_IN_REPORTS_MASK
        else:
            self.options = self.options & ~INCLUDE_IN_REPORTS_MASK

    @hybrid_property
    def send_reminders(self):
        return self.options & SEND_REMINDERS_MASK

    @send_reminders.setter
    def send_reminders(self, value):
        if value:
            self.options = self.options | SEND_REMINDERS_MASK
        else:
            self.options = self.options & ~SEND_REMINDERS_MASK

    def as_json(self):
        d = {}
        d['user_id'] = self.user_id
        d['organization_id'] = self.organization_id
        d['signed'] = FHIR_datetime.as_fhir(self.audit.timestamp)
        d['expires'] = FHIR_datetime.as_fhir(self.expires)
        d['agreement_url'] = self.agreement_url
        if self.deleted_id:
            d['deleted'] = self.deleted.as_fhir()
        if self.options:
            for attr in ('staff_editable', 'include_in_reports',
                         'send_reminders'):
                if getattr(self, attr):
                    d[attr] = True
        return d

    @classmethod
    def from_json(cls, data):
        user = User.query.get(data.get('user_id'))
        if not user:
            raise ValueError("required user_id not found")
        org = Organization.query.get(data.get('organization_id'))
        if not org:
            raise ValueError("required organization_id not found")
        url = data.get('agreement_url')
        try:
            url_validation(url)
        except:
            raise ValueError("requires a valid agreement_url")

        obj = cls(
            user_id=data['user_id'], organization_id=data['organization_id'],
            agreement_url=data['agreement_url'])

        for attr in (
            'staff_editable', 'include_in_reports', 'send_reminders'):
            if attr in data:
                setattr(obj, attr, data.get(attr))

        return obj
