import sqlalchemy as sa
from alembic import op

"""empty message

Revision ID: e3923b19b6f5
Revises: eff963021768
Create Date: 2017-09-14 11:48:47.116937

"""

# revision identifiers, used by Alembic.
revision = 'e3923b19b6f5'
down_revision = 'eff963021768'


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # We'll recreate the QBs after via site_persistence.  Drop
    # now to avoid upgrade problems
    op.execute(
        "UPDATE questionnaire_responses SET questionnaire_bank_id = null")
    op.execute("DELETE FROM questionnaire_bank_questionnaires")
    op.execute("DELETE FROM questionnaire_banks")

    op.create_table(
        'questionnaire_bank_recurs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'questionnaire_bank_id',
            sa.Integer(),
            nullable=False),
        sa.Column('recur_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['questionnaire_bank_id'],
            ['questionnaire_banks.id'],
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['recur_id'],
            ['recurs.id'],
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'questionnaire_bank_id',
            'recur_id',
            name='_questionnaire_bank_recure')
    )
    op.drop_table('questionnaire_bank_questionnaire_recurs')
    op.drop_column('questionnaire_bank_questionnaires', 'days_till_overdue')
    op.drop_column('questionnaire_bank_questionnaires', 'days_till_due')
    op.add_column(
        'questionnaire_banks',
        sa.Column(
            'expired',
            sa.Text(),
            nullable=True))
    op.add_column(
        'questionnaire_banks',
        sa.Column(
            'overdue',
            sa.Text(),
            nullable=True))
    op.add_column(
        'questionnaire_banks',
        sa.Column(
            'start',
            sa.Text(),
            nullable=False))
    op.add_column(
        'recurs',
        sa.Column(
            'cycle_length',
            sa.Text(),
            nullable=False))
    op.add_column('recurs', sa.Column('start', sa.Text(), nullable=False))
    op.add_column('recurs', sa.Column('termination', sa.Text(), nullable=True))
    op.drop_constraint(u'_unique_recur', 'recurs', type_='unique')
    op.create_unique_constraint(
        '_unique_recur', 'recurs', [
            'start', 'cycle_length', 'termination'])
    op.drop_column('recurs', 'days_till_termination')
    op.drop_column('recurs', 'days_in_cycle')
    op.drop_column('recurs', 'days_to_start')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        'recurs',
        sa.Column(
            'days_to_start',
            sa.INTEGER(),
            autoincrement=False,
            nullable=False))
    op.add_column(
        'recurs',
        sa.Column(
            'days_in_cycle',
            sa.INTEGER(),
            autoincrement=False,
            nullable=False))
    op.add_column(
        'recurs',
        sa.Column(
            'days_till_termination',
            sa.INTEGER(),
            autoincrement=False,
            nullable=True))
    op.drop_constraint('_unique_recur', 'recurs', type_='unique')
    op.create_unique_constraint(
        u'_unique_recur', 'recurs', [
            'days_to_start', 'days_in_cycle', 'days_till_termination'])
    op.drop_column('recurs', 'termination')
    op.drop_column('recurs', 'start')
    op.drop_column('recurs', 'cycle_length')
    op.drop_column('questionnaire_banks', 'start')
    op.drop_column('questionnaire_banks', 'overdue')
    op.drop_column('questionnaire_banks', 'expired')
    op.add_column(
        'questionnaire_bank_questionnaires',
        sa.Column(
            'days_till_due',
            sa.INTEGER(),
            autoincrement=False,
            nullable=False))
    op.add_column(
        'questionnaire_bank_questionnaires',
        sa.Column(
            'days_till_overdue',
            sa.INTEGER(),
            autoincrement=False,
            nullable=False))
    op.create_table(
        'questionnaire_bank_questionnaire_recurs',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column(
            'questionnaire_bank_questionnaire_id',
            sa.INTEGER(),
            autoincrement=False,
            nullable=False),
        sa.Column(
            'recur_id',
            sa.INTEGER(),
            autoincrement=False,
            nullable=False),
        sa.ForeignKeyConstraint(
            ['questionnaire_bank_questionnaire_id'],
            [u'questionnaire_bank_questionnaires.id'],
            name=(u'questionnaire_bank_questionna_questionnaire'
                  '_bank_questionn_fkey'),
            ondelete=u'CASCADE'),
        sa.ForeignKeyConstraint(
            ['recur_id'],
            [u'recurs.id'],
            name=u'questionnaire_bank_questionnaire_recurs_recur_id_fkey',
            ondelete=u'CASCADE'),
        sa.PrimaryKeyConstraint(
            'id', name=u'questionnaire_bank_questionnaire_recurs_pkey'),
        sa.UniqueConstraint(
            'questionnaire_bank_questionnaire_id',
            'recur_id',
            name=u'_questionnaire_bank_questionnaire_recure')
    )
    op.drop_table('questionnaire_bank_recurs')
    # ### end Alembic commands ###
