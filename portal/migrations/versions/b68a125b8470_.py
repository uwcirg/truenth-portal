"""empty message

Revision ID: b68a125b8470
Revises: 57c7302610d1
Create Date: 2017-03-07 16:37:44.598935

"""

# revision identifiers, used by Alembic.
revision = 'b68a125b8470'
down_revision = '57c7302610d1'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('procedures', sa.Column(
        'encounter_id', sa.Integer(), nullable=True))
    op.create_foreign_key('procedures_encounter_fk',
                          'procedures', 'encounters', ['encounter_id'], ['id'])
    op.add_column('questionnaire_responses', sa.Column(
        'encounter_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'qr_encounter_id_fk',
        'questionnaire_responses',
        'encounters',
        ['encounter_id'],
        ['id'])
    op.add_column('user_observations', sa.Column(
        'encounter_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'user_observation_encounter_id_fk',
        'user_observations',
        'encounters',
        ['encounter_id'],
        ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('user_observation_encounter_id_fk',
                       'user_observations', type_='foreignkey')
    op.drop_column('user_observations', 'encounter_id')
    op.drop_constraint('qr_encounter_id_fk',
                       'questionnaire_responses', type_='foreignkey')
    op.drop_column('questionnaire_responses', 'encounter_id')
    op.drop_constraint('procedures_encounter_fk',
                       'procedures', type_='foreignkey')
    op.drop_column('procedures', 'encounter_id')
    # ### end Alembic commands ###
