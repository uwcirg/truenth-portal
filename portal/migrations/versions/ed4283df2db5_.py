"""STAFF_ADMIN role stands alone - remove STAFF role from current STAFF_ADMINs

Revision ID: ed4283df2db5
Revises: 30f20e54eb5c
Create Date: 2020-08-31 11:12:30.249107

"""
from alembic import op
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

from portal.models.role import ROLE, Role
from portal.models.user import UserRoles

# revision identifiers, used by Alembic.
revision = 'ed4283df2db5'
down_revision = '30f20e54eb5c'

Session = sessionmaker()


def all_staff_admins(session):
    """returns list of all staff admins user ids"""
    staff_admin_role_id = session.query(Role).filter(
        Role.name == ROLE.STAFF_ADMIN.value).with_entities(Role.id).one()
    return [ur.user_id for ur in session.query(UserRoles).filter(
        UserRoles.role_id == staff_admin_role_id)]


def staff_role_id(session):
    """return staff role id"""
    return session.query(Role).filter(
        Role.name == ROLE.STAFF.value).with_entities(Role.id).one()[0]


def upgrade():
    """Remove the STAFF role from existing STAFF_ADMIN accounts"""
    bind = op.get_bind()
    session = Session(bind=bind)

    conn = op.get_bind()
    conn.execute(text(
        "DELETE FROM user_roles WHERE role_id = :staff_id and"
        " user_id in :staff_admin_ids"),
        staff_id=staff_role_id(session),
        staff_admin_ids=tuple(all_staff_admins(session)))


def downgrade():
    """Reapply the STAFF role to existing STAFF_ADMIN accounts"""
    bind = op.get_bind()
    session = Session(bind=bind)

    conn = op.get_bind()
    staff_id = staff_role_id()
    for user_id in all_staff_admins(session):
        conn.execute(text(
            "INSERT INTO user_roles (user_id, role_id) VALUES "
            "(:user_id, :role_id)"),
            user_id=user_id,
            role_id=staff_id)
