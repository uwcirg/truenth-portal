"""empty message

Revision ID: 418982ee27e2
Revises: 0ac4b88c909f
Create Date: 2017-05-02 12:05:13.995805

"""

# revision identifiers, used by Alembic.
revision = '418982ee27e2'
down_revision = '0ac4b88c909f'

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('questionnaires',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.Text(), nullable=False),
                    sa.Column('document', postgresql.JSONB(
                        astext_type=sa.Text()), nullable=True),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('name')
                    )
    op.create_table('questionnaire_banks',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.Text(), nullable=False),
                    sa.Column('organization_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['organization_id'], [
                                            'organizations.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('name')
                    )
    op.create_table('questionnaire_bank_questionnaires',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('questionnaire_bank_id',
                              sa.Integer(), nullable=False),
                    sa.Column('questionnaire_id',
                              sa.Integer(), nullable=False),
                    sa.Column('days_till_due', sa.Integer(), nullable=False),
                    sa.Column('days_till_overdue',
                              sa.Integer(), nullable=False),
                    sa.Column('rank', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['questionnaire_bank_id'], [
                        'questionnaire_banks.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['questionnaire_id'], [
                        'questionnaires.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('questionnaire_bank_id', 'questionnaire_id',
                                        name='_questionnaire_bank_questionnaire'),
                    sa.UniqueConstraint('questionnaire_id', 'rank',
                                        name='_questionnaire_bank_questionnaire_rank')
                    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('questionnaire_bank_questionnaires')
    op.drop_table('questionnaire_banks')
    op.drop_table('questionnaires')
    # ### end Alembic commands ###
