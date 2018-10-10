from alembic import op
from flask import current_app
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.models.audit import Audit
from portal.models.encounter import initiate_encounter
from portal.models.clinical_constants import CC
from portal.models.organization import (
    Organization,
    OrgTree,
    UserOrganization,
)
from portal.models.user import User, UserRoles
from portal.models.role import Role


"""Add PCa_localized observation to LOCALIZED_AFFILIATE_ORG

Revision ID: b4dcf331317e
Revises: c49b7f7944a7
Create Date: 2018-07-03 11:35:59.494239

"""

# revision identifiers, used by Alembic.
revision = 'b4dcf331317e'
down_revision = 'c49b7f7944a7'
Session = sessionmaker()


def upgrade():
    localized_org = current_app.config.get('LOCALIZED_AFFILIATE_ORG')
    if not localized_org:
        return

    bind = op.get_bind()
    session = Session(bind=bind)

    admin = User.query.filter_by(email='bob25mary@gmail.com').first()
    admin = admin or User.query.join(
        UserRoles).join(Role).filter(
        sa.and_(
            Role.id == UserRoles.role_id, UserRoles.user_id == User.id,
            Role.name == 'admin')).first()
    admin_id = admin.id

    # encounter needed to save_observation
    initiate_encounter(admin, "staff_authenticated")

    localized_org_id = session.query(Organization).filter(
        Organization.name == localized_org).one().id
    patient_id = session.query(Role).filter(Role.name == 'patient').one().id
    org_list = OrgTree().here_and_below_id(localized_org_id)

    query = User.query.join(UserOrganization).join(UserRoles).filter(sa.and_(
        User.id == UserOrganization.user_id,
        User.id == UserRoles.user_id,
        UserRoles.role_id == patient_id,
        UserOrganization.organization_id.in_(org_list))).with_entities(User)

    for user in query:
        if user.concept_value(CC.PCaLocalized) == 'true':
            # user already has positive PCaLocalized observation
            continue
        else:
            audit = Audit(
                user_id=admin_id, subject_id=patient_id,
                context='observation')
            user.save_observation(
                codeable_concept=CC.PCaLocalized,
                value_quantity=CC.TRUE_VALUE,
                audit=audit, status=None, issued=None)
            audit.comment = "set {0} {1} on user {2}".format(
                CC.PCaLocalized, CC.TRUE_VALUE, patient_id)

    session.commit()


def downgrade():
    # Harmless to leave localized observation in tact (and difficult to
    # determine if it was added by migration above
    pass
