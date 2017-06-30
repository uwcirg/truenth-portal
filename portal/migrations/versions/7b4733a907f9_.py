"""empty message

Revision ID: 7b4733a907f9
Revises: af193c376724
Create Date: 2017-06-29 15:47:18.705366

"""

# revision identifiers, used by Alembic.
revision = '7b4733a907f9'
down_revision = 'af193c376724'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('scheduled_jobs',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('task', sa.Text(), nullable=False),
                    sa.Column('args', sa.Text(), nullable=True),
                    sa.Column('schedule', sa.Text(), nullable=False),
                    sa.Column('active', sa.Boolean(),
                              server_default='1', nullable=False),
                    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('scheduled_jobs')
