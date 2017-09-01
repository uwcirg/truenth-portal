"""empty message

Revision ID: 936971a9b55d
Revises: f9d108978c5a
Create Date: 2016-05-04 00:43:53.278725

"""

# revision identifiers, used by Alembic.
revision = '936971a9b55d'
down_revision = 'f9d108978c5a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'performers',
        sa.Column(
            'id',
            sa.Integer(),
            nullable=False),
        sa.Column(
            'reference_txt',
            sa.Text(),
            nullable=False),
        sa.Column(
            'codeable_concept_id',
            sa.Integer(),
            nullable=True),
        sa.ForeignKeyConstraint(
            ['codeable_concept_id'],
            ['codeable_concepts.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'reference_txt',
            'codeable_concept_id',
            name='_reftxt_codeable_concept'))
    op.create_table(
        'observation_performers',
        sa.Column(
            'id',
            sa.Integer(),
            nullable=False),
        sa.Column(
            'observation_id',
            sa.Integer(),
            nullable=False),
        sa.Column(
            'performer_id',
            sa.Integer(),
            nullable=False),
        sa.ForeignKeyConstraint(
            ['observation_id'],
            ['observations.id'],
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['performer_id'],
            ['performers.id'],
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'observation_id',
            'performer_id',
            name='_obs_performer'))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('observation_performers')
    op.drop_table('performers')
    ### end Alembic commands ###
