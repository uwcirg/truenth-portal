"""empty message

Revision ID: 55a29f2ab55d
Revises: 1df2ef1f5b73
Create Date: 2015-10-14 10:16:28.732951

"""

# revision identifiers, used by Alembic.
revision = '55a29f2ab55d'
down_revision = '1df2ef1f5b73'

import sqlalchemy as sa
from alembic import op


def upgrade():
    # google ids won't fit in bigint - make a string
    # have to convert existing
    op.execute("ALTER TABLE auth_providers ALTER COLUMN provider_id "
               "TYPE varchar(40) USING (provider_id)")


def downgrade():
    op.execute("ALTER TABLE auth_providers ALTER COLUMN provider_id "
               "TYPE bigint USING CAST(provider_id AS bigint)")
