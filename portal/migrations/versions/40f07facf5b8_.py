"""empty message

Revision ID: 40f07facf5b8
Revises: 7ad0da0d1b72
Create Date: 2017-07-13 12:18:08.568480

"""

# revision identifiers, used by Alembic.
revision = '40f07facf5b8'
down_revision = '7ad0da0d1b72'

from alembic import op


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(
        '_unique_recur', 'recurs', [
            'days_to_start', 'days_in_cycle', 'days_till_termination'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('_unique_recur', 'recurs', type_='unique')
    # ### end Alembic commands ###
