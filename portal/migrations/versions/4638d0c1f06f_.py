"""empty message

Revision ID: 4638d0c1f06f
Revises: 3cc747cb00c3
Create Date: 2016-03-24 11:46:52.925858

"""

# revision identifiers, used by Alembic.
revision = '4638d0c1f06f'
down_revision = '3cc747cb00c3'

import sqlalchemy as sa
from alembic import op


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_ethnicities',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=True),
                    sa.Column('codeable_concept_id',
                              sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['codeable_concept_id'], [
                        'codeable_concepts.id'], ),
                    sa.ForeignKeyConstraint(
                        ['user_id'], ['users.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('user_races',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=True),
                    sa.Column('codeable_concept_id',
                              sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['codeable_concept_id'], [
                        'codeable_concepts.id'], ),
                    sa.ForeignKeyConstraint(
                        ['user_id'], ['users.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('user_races')
    op.drop_table('user_ethnicities')
    ### end Alembic commands ###
