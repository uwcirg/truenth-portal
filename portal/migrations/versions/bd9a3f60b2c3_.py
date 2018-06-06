from alembic import op
from sqlalchemy.orm import sessionmaker

"""Clean up protected roles

Revision ID: bd9a3f60b2c3
Revises: df7f10d6fd60
Create Date: 2018-04-09 15:40:29.889685

"""
# revision identifiers, used by Alembic.
revision = 'bd9a3f60b2c3'
down_revision = 'df7f10d6fd60'

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


def downgrade():
    # no reverse step
    pass
