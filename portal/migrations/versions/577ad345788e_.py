"""empty message

Revision ID: 577ad345788e
Revises: 3b655c2d1a85
Create Date: 2015-11-17 11:18:22.685983

"""

# revision identifiers, used by Alembic.
revision = '577ad345788e'
down_revision = '3b655c2d1a85'

import sqlalchemy as sa
from alembic import op


def upgrade():
    command = """
    ALTER TABLE auth_providers
    DROP CONSTRAINT auth_providers_user_id_fkey,
    ADD CONSTRAINT auth_providers_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
    """
    op.execute(command)


def downgrade():
    command = """
    ALTER TABLE auth_providers
    DROP CONSTRAINT auth_providers_user_id_fkey,
    ADD CONSTRAINT auth_providers_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id)
    """
    op.execute(command)
