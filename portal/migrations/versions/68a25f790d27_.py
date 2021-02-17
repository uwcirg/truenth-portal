"""trigger_states gains visit_month column

Revision ID: 68a25f790d27
Revises: 7fd6b3abfec2
Create Date: 2020-12-08 14:17:28.279106

"""
from alembic import op
from flask import current_app
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '68a25f790d27'
down_revision = '7fd6b3abfec2'


def upgrade():
    if current_app.config.get('GIL'):
        return
    op.add_column(
        'trigger_states',
        sa.Column('visit_month', sa.Integer()))
    op.execute(
        "UPDATE trigger_states SET visit_month = 0")
    op.alter_column('trigger_states', 'visit_month', nullable=False)
    op.create_index(
        op.f('ix_trigger_states_visit_month'),
        'trigger_states',
        ['visit_month'],
        unique=False)


def downgrade():
    if current_app.config.get('GIL'):
        return
    op.drop_index(
        op.f('ix_trigger_states_visit_month'),
        table_name='trigger_states')
    op.drop_column('trigger_states', 'visit_month')
