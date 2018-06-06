"""empty message

Revision ID: 521aa70e0617
Revises: 491d8352bfc3
Create Date: 2015-08-20 00:48:47.773253

"""

# revision identifiers, used by Alembic.
revision = '521aa70e0617'
down_revision = '491d8352bfc3'

import sqlalchemy as sa
from alembic import op


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('image_url', sa.Text(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'image_url')
    ### end Alembic commands ###
