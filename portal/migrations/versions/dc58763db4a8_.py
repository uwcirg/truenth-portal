import sqlalchemy as sa
from alembic import op

"""empty message

Revision ID: dc58763db4a8
Revises: 9b1bedfa916b
Create Date: 2017-11-01 15:43:41.695937

"""

# revision identifiers, used by Alembic.
revision = 'dc58763db4a8'
down_revision = '9b1bedfa916b'


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('organizations', sa.Column('timezone', sa.String(length=20), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('organizations', 'timezone')
    # ### end Alembic commands ###
