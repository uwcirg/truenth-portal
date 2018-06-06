"""Clean up protected roles

Revision ID: 3271a78bbc8b
Revises: 1b7b8092fcef
Create Date: 2018-04-24 09:37:47.003826

"""
from alembic import op
from sqlalchemy.orm import sessionmaker

# revision identifiers, used by Alembic.
revision = '3271a78bbc8b'
down_revision = '1b7b8092fcef'

Session = sessionmaker()


def upgrade():
    # Users that have registered should not have restricted roles
    # such as `access_on_verify` or `write_only`.  Remove if found
    bind = op.get_bind()
    session = Session(bind=bind)

    # Kill those with set passwords
    session.execute("""
            DELETE FROM user_roles WHERE id IN (
            SELECT user_roles.id FROM users
            JOIN user_roles ON users.id = user_id
            JOIN roles ON roles.id = role_id
            WHERE password IS NOT NULL
            AND roles.name IN ('access_on_verify', 'write_only',
            'promote_without_identity_challenge'))""")

    # .. and those with auth_providers
    session.execute("""
            DELETE FROM user_roles WHERE id IN (
            SELECT user_roles.id FROM users
            JOIN user_roles ON users.id = user_roles.user_id
            JOIN roles ON roles.id = role_id
            JOIN auth_providers ON users.id = auth_providers.user_id
            WHERE roles.name IN ('access_on_verify', 'write_only',
            'promote_without_identity_challenge'))""")
    session.commit()


def downgrade():
    # no reverse step
    pass
