"""give non-registered `write_only`

Revision ID: 773b1de060dd
Revises: 1b7b8092fcef
Create Date: 2018-04-23 12:49:17.756737

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from portal.models.audit import Audit
from portal.models.role import Role
from portal.models.user import User, UserRoles

Session = sessionmaker()

# revision identifiers, used by Alembic.
revision = '773b1de060dd'
down_revision = '1b7b8092fcef'


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    admin = User.query.filter_by(email='bob25mary@gmail.com').first()
    admin = admin or User.query.join(
        UserRoles).join(Role).filter(
        sa.and_(
            Role.id == UserRoles.role_id, UserRoles.user_id == User.id,
            Role.name == 'admin')).first()
    admin_id = admin.id

    write_role_id = session.execute(
        """SELECT id FROM roles WHERE name = 'write_only'""").fetchone()[0]
    query = """
        SELECT id as user_id FROM users WHERE password IS NULL and id NOT IN (
            SELECT user_id FROM auth_providers) AND id NOT IN (
            SELECT user_id
            FROM user_roles
            WHERE role_id IN (
            SELECT id
            FROM roles
            WHERE name IN (
              'access_on_verify', 'write_only', 'promote_without_identity_challenge')
            )
          )
    """
    insert = text(
        """INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)""")

    user_ids = [u_id[0] for u_id in session.execute(query)]
    for user_id in user_ids:
        session.execute(insert, {'user_id': user_id, 'role_id': write_role_id})
        aud = Audit(
            user_id=admin_id,
            subject_id=user_id,
            context='role',
            comment="add 'write_only' via migration to non-registered w/o special role")
        session.add(aud)
    session.commit()


def downgrade():
    """no value seen in restoring - audits exist if determined necessary"""
    pass
