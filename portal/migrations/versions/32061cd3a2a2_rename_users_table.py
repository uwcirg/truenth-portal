"""pluralize table names

Revision ID: 32061cd3a2a2
Revises: 4f7e2f9ff54e
Create Date: 2015-06-22 16:26:24.166887

"""

# revision identifiers, used by Alembic.
revision = '32061cd3a2a2'
down_revision = '4f7e2f9ff54e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.rename_table('user', 'users')
    op.rename_table('client', 'clients')
    op.rename_table('grant', 'grants')
    op.rename_table('token', 'tokens')


def downgrade():
    op.rename_table('users', 'user')
    op.rename_table('clients', 'client')
    op.rename_table('grants', 'grant')
    op.rename_table('tokens', 'token')
