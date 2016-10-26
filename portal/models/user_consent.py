"""User Consent module"""
from datetime import datetime, timedelta
from validators import url as url_validation

from .audit import Audit
from ..extensions import db
from .fhir import FHIR_datetime
from .organization import Organization, OrgTree
from .user import User

def default_expires():
    """5 year from now, in UTC"""
    return datetime.utcnow() + timedelta(days=365*5)


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

    audit = db.relationship(Audit, cascade="save-update",
                            foreign_keys=[audit_id])
    deleted = db.relationship(Audit, cascade="save-update",
                              foreign_keys=[deleted_id])
    organization = db.relationship(Organization, cascade="save-update")

    def __str__(self):
        return ("user_consent at {0.agreement_url} between {0.user_id} and "
                "{0.organization_id}".format(self))

    def as_json(self):
        d = {}
        d['user_id'] = self.user_id
        d['organization_id'] = self.organization_id
        d['signed'] = FHIR_datetime.as_fhir(self.audit.timestamp)
        d['expires'] = FHIR_datetime.as_fhir(self.expires)
        d['agreement_url'] = self.agreement_url
        if self.deleted_id:
            d['deleted'] = FHIR_datetime.as_fhir(self.deleted.timestamp)

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

        return cls(user_id=data['user_id'],
                   organization_id=data['organization_id'],
                   agreement_url=data['agreement_url'])

def fake_consents():
    """Bootstrap method as we transition from org relations to consent

    Expected as a one time development trick to create fake consent
    agreements between users and the orgs they currently belong to.

    Should probably have a short life (i.e. delete this code and the
    manager.command if it no longer makes sense).

    """
    from .organization import UserOrganization

    admin_id = User.query.filter_by(email='bob25mary@gmail.com').one().id

    # Track down all users with org associations
    users_orgs = db.session.query(User, UserOrganization).filter(
        User.id == UserOrganization.user_id).distinct(
            User.id).group_by(User.id, UserOrganization.id)
    for user, user_org in users_orgs:
        org = user_org.organization
        # None of the above doesn't apply
        if org.name == 'none of the above':
            continue

        # lookup top-level organization for consent
        top_id = OrgTree().find(org.id).top_level()

        existing_org_consents = [uc.organization_id for uc in
                                 user.valid_consents]
        if top_id not in existing_org_consents:
            audit = Audit(user_id=admin_id, comment='fake consent added')
            uc = UserConsent(
                user_id=user.id, organization_id=top_id, audit=audit,
                agreement_url='http://fake-consent.org')
            db.session.add(uc)
    db.session.commit()
