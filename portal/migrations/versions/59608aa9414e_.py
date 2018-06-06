"""empty message

Revision ID: 59608aa9414e
Revises: 91c2bd4689a
Create Date: 2015-09-28 12:36:05.708632

"""

# revision identifiers, used by Alembic.
revision = '59608aa9414e'
down_revision = '91c2bd4689a'

import sqlalchemy as sa
from alembic import op


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('roles', sa.Column('description', sa.Text(), nullable=True))
    op.create_unique_constraint(
        '_user_role', 'user_roles', ['user_id', 'role_id'])
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('_user_role', 'user_roles', type_='unique')
    op.drop_column('roles', 'description')
    ### end Alembic commands ###
