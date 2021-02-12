"""merge together hotfix and develop migrations

Revision ID: 451d5b4a8882
Revises: ('b3c0554cde0e', 'ed4283df2db5')
Create Date: 2020-09-15 22:00:07.212844

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '451d5b4a8882'
down_revision = ('b3c0554cde0e', 'ed4283df2db5')


def upgrade():
    pass


def downgrade():
    pass
