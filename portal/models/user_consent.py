"""User Consent module"""
from datetime import datetime, timedelta

from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.ext.hybrid import hybrid_property
from validators import ValidationFailure, url as url_validation

from ..database import db
from ..date_tools import FHIR_datetime, utcnow_sans_micro
from .audit import Audit
from .organization import Organization
from .user import User


def default_expires():
    """5 year from now, in UTC"""
    return datetime.utcnow() + timedelta(days=365 * 5)


STAFF_EDITABLE_MASK = 0b001
INCLUDE_IN_REPORTS_MASK = 0b010
SEND_REMINDERS_MASK = 0b100

status_types = ('consented', 'suspended', 'deleted')
status_types_enum = ENUM(
    *status_types, name='status_enum', create_type=False)


class UserConsent(db.Model):
    """ORM class for user_consent data

    Capture data when user consents to share data with an organization.

    """
    __tablename__ = 'user_consents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False, index=True)
    organization_id = db.Column(
        db.ForeignKey('organizations.id'), nullable=False)
    acceptance_date = db.Column(
        db.DateTime, default=utcnow_sans_micro, nullable=False)
    audit_id = db.Column(db.ForeignKey('audit.id'), nullable=False)
    deleted_id = db.Column(db.ForeignKey('audit.id'), nullable=True)
    expires = db.Column(db.DateTime, default=default_expires, nullable=False)
    agreement_url = db.Column(db.Text, nullable=False)
    options = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column('status', status_types_enum,
                       server_default='consented', nullable=False)
    research_study_id = db.Column(
        db.ForeignKey('research_studies.id', ondelete='cascade'),
        nullable=False)

    audit = db.relationship(Audit, cascade="save-update, delete",
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
        d['acceptance_date'] = FHIR_datetime.as_fhir(self.acceptance_date)
        d['expires'] = FHIR_datetime.as_fhir(self.expires)
        d['agreement_url'] = self.agreement_url
        d['recorded'] = self.audit.as_fhir()
        if self.deleted_id:
            d['deleted'] = self.deleted.as_fhir()
        if self.options:
            for attr in ('staff_editable', 'include_in_reports',
                         'send_reminders'):
                if getattr(self, attr):
                    d[attr] = True
        d['status'] = self.status
        d['research_study_id'] = self.research_study_id
        return d

    @classmethod
    def from_json(cls, data):
        user = 'user_id' in data and User.query.get(data['user_id'])
        if not user:
            raise ValueError("required user_id not found")
        if 'organization_id' not in data:
            raise ValueError("required organization_id not found")
        org_id = int(data.get('organization_id'))
        if not Organization.query.get(org_id):
            raise ValueError("organization not found for id {}".format(org_id))
        url = data.get('agreement_url')
        try:
            url_validation(url)
        except ValidationFailure:
            raise ValueError("requires a valid agreement_url")

        obj = cls(
            user_id=data['user_id'], organization_id=org_id,
            agreement_url=data['agreement_url'])

        if data.get('expires'):
            obj.expires = FHIR_datetime.parse(
                data.get('expires'), error_subject='expires')
        if data.get('acceptance_date'):
            obj.acceptance_date = FHIR_datetime.parse(
                data.get('acceptance_date'), error_subject='acceptance_date')
        for attr in ('staff_editable', 'include_in_reports',
                     'send_reminders', 'status', 'research_study_id'):
            if attr in data:
                if attr == 'status' and data.get(attr) not in status_types:
                    raise ValueError(f"ill defined user_consent.status: {data.get(attr)}")
                setattr(obj, attr, data.get(attr))

        return obj


def latest_consent(user, research_study_id):
    """Lookup latest valid consent for user

    :param user: subject of query
    :param research_study_id: limit query to respective value

    If latest consent for user is 'suspended' or 'deleted', this function
    will return None.  See ``consent_withdrawal_dates()`` for that need.

    :returns: the most recent consent based on given criteria, or None
        if no match is located

    """
    # consents are ordered desc(acceptance_date)
    for consent in user.valid_consents:
        if consent.research_study_id != research_study_id:
            continue
        if consent.status == 'consented':
            return consent

    return None


def consent_withdrawal_dates(user, research_study_id):
    """Lookup user's most recent consent and withdrawal dates

    In a currently withdrawn case, lookup the date of withdrawal and the
    acceptance_date of the consent prior to withdrawal.

    If the user isn't currently withdrawn, simply return the current
    consent and None for withdrawal date.

    :param user: subject of query
    :param research_study_id: limit query to consents with respective value
    :returns: (consent_date, withdrawal_date) for user.  Either value
        may be None if not found.

    """
    withdrawal_date = None
    consent = latest_consent(user, research_study_id=research_study_id)
    if consent:
        # Valid consent found, user hasn't withdrawn; leave
        return consent.acceptance_date, withdrawal_date

    # Look for withdrawn case.  If found, also look up the previous
    # consent date (prior to withdrawal)

    prior_acceptance = None
    for consent in user.all_consents:
        if consent.research_study_id != research_study_id:
            continue
        if not withdrawal_date and (
                consent.status == 'suspended' and not consent.deleted_id):
            withdrawal_date = consent.acceptance_date
            if prior_acceptance:
                raise ValueError(
                    "don't expect prior acceptance before withdrawal date")
        if consent.status == 'deleted' and withdrawal_date:
            prior_acceptance = consent.acceptance_date
            # situation where consent date was changed before withdrawal
            # requires we continue to look and use last found (don't break!)

    return prior_acceptance, withdrawal_date
