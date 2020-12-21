"""ToU (Terms of Use)  module"""
from sqlalchemy.dialects.postgresql import ENUM

from ..database import db
from ..date_tools import FHIR_datetime
from .notification import Notification, UserNotification
from .organization import Organization, OrgTree
from .role import ROLE, Role
from .user import User
#TODO check if it is right to add the extra TOU type here? Migration needed then?
tou_types = ENUM('website terms of use', 'subject website consent',
                 'stored website consent form', 'privacy policy',
                 'EMPRO website terms of use',
                 name='tou_types', create_type=False)


class ToU(db.Model):
    """SQLAlchemy class for `tou` table"""
    __tablename__ = 'tou'
    id = db.Column(db.Integer(), primary_key=True)
    agreement_url = db.Column(
        db.Text, server_default='predates agreement_url', nullable=False)
    audit_id = db.Column(db.ForeignKey('audit.id'), nullable=False)
    organization_id = db.Column(db.ForeignKey('organizations.id'))
    type = db.Column('type', tou_types, nullable=False)
    active = db.Column(db.Boolean(), nullable=False, server_default='1')

    audit = db.relationship('Audit', cascade="save-update", lazy='joined')
    """tracks when and by whom the terms were agreed to"""

    def __str__(self):
        return "ToU ({0.audit}) {0.agreement_url}".format(self)

    def as_json(self):
        d = {}
        d['id'] = self.id
        d['agreement_url'] = self.agreement_url
        d['accepted'] = FHIR_datetime.as_fhir(self.audit.timestamp)
        d['type'] = self.type
        if self.organization_id:
            d['organization_id'] = self.organization_id
        d['active'] = self.active
        return d


def update_tous(
        types, organization=None, roles=None, notification=None,
        deactivate=False, job_id=None, manual_run=None):
    """Used to notify user and potentially deactivate matching ToU agreements

    When the Terms of Use are updated, this will mark the existing, matching
    terms as inactive (if requested via the deactivate param) and create a
    notification (if requested via the notification param) message to display
    to the user on next login.

    :param types: list of ToU types; see ``tou.tou_types`` for valid options
    :param organization: Provide name of organization to restrict
     to respective set of users (all child orgs implicitly included)
    :param roles: Restrict to users with given roles; defaults to
     (ROLE.PATIENT.value, ROLE.STAFF.value, ROLE.STAFF_ADMIN.value)
    :param notification: Name the notification to trigger, if applicable
    :param deactivate: set True to deactivate matching consents
    :param job_id: Used by scheduler - ignored in this context
    :param manual_run: Used by scheduler - ignored in this context

    """
    # Need system user if deactivating, for audit
    sys = User.query.filter_by(email='__system__').first()
    if deactivate and not sys:
        raise ValueError("No system user found")

    # Validate args and build the respective sets

    require_orgs = None
    if organization:
        org = Organization.query.filter(
            Organization.name == organization).first()
        if not org:
            raise ValueError("No such organization: {}".format(organization))
        require_orgs = set(OrgTree().here_and_below_id(org.id))

    require_roles = (
        set(roles) if roles else
        {ROLE.PATIENT.value, ROLE.STAFF.value, ROLE.STAFF_ADMIN.value})
    for role in require_roles:
        if not Role.query.filter(Role.name == role).first():
            raise ValueError("No such role: {}".format(role))

    notif = None
    if notification:
        notif = Notification.query.filter_by(name=notification).first()
        if not notif:
            raise ValueError("Notification `{}` not found".format(notification))

    # For each applicable user, deactivate matching tous and add a notification
    # as requested
    for user in User.query.filter(User.deleted_id.is_(None)):
        if require_roles.isdisjoint([r.name for r in user.roles]):
            continue
        if require_orgs and require_orgs.isdisjoint(
                [o.id for o in user.organizations]):
            continue
        if deactivate:
            user.deactivate_tous(acting_user=sys, types=types)
        if notif:
            if not UserNotification.query.filter_by(
                    user_id=user.id, notification_id=notif.id).count():
                un = UserNotification(user_id=user.id,
                                      notification_id=notif.id)
                db.session.add(un)
    db.session.commit()
