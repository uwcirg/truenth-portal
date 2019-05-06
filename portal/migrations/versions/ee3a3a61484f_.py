"""flush qb_timeline cache for all suspended patients, take 3

Revision ID: ee3a3a61484f
Revises: 4ea2b79957f3
Create Date: 2019-05-06 15:48:37.451276

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'ee3a3a61484f'
down_revision = '4ea2b79957f3'


def upgrade():
    expr = "delete from qb_timeline where user_id in (" \
           "select user_id from user_consents where status = 'suspended')"
    op.execute(expr)


def downgrade():
    pass
