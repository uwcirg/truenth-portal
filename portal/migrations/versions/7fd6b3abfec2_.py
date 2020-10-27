"""TriggerStates table - for EPROMs only blueprint `trigger_states`

Revision ID: 7fd6b3abfec2
Revises: 1675585e7031
Create Date: 2020-10-15 02:55:21.369483

"""
from alembic import op
from flask import current_app
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7fd6b3abfec2'
down_revision = '1675585e7031'


def upgrade():
    if current_app.config.get('GIL'):
        return
    op.create_table(
        'trigger_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column(
            'state',
            postgresql.ENUM(
                'unstarted',
                'due',
                'processed',
                name='trigger_state_type'),
            nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column(
            'triggers',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    op.create_index(
        op.f('ix_trigger_states_state'),
        'trigger_states',
        ['state'],
        unique=False)
    op.create_index(
        op.f('ix_trigger_states_timestamp'),
        'trigger_states',
        ['timestamp'],
        unique=False)
    op.create_index(
        op.f('ix_trigger_states_user_id'),
        'trigger_states',
        ['user_id'],
        unique=False)
    # ### end Alembic commands ###


def downgrade():
    if current_app.config.get('GIL'):
        return
    op.drop_index(
        op.f('ix_trigger_states_user_id'), table_name='trigger_states')
    op.drop_index(
        op.f('ix_trigger_states_timestamp'), table_name='trigger_states')
    op.drop_index(
        op.f('ix_trigger_states_state'), table_name='trigger_states')
    op.drop_table('trigger_states')
    # ### end Alembic commands ###
