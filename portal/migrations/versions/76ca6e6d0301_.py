import sqlalchemy as sa
from alembic import op

"""empty message

Revision ID: 76ca6e6d0301
Revises: 40b223faa7d4
Create Date: 2018-01-26 11:11:48.826887

"""

# revision identifiers, used by Alembic.
revision = '76ca6e6d0301'
down_revision = '40b223faa7d4'


def upgrade():
    op.create_table(
        'practitioners',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(length=64), nullable=True),
        sa.Column('last_name', sa.String(length=64), nullable=False),
        sa.Column('phone_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['phone_id'], ['contact_points.id'],
                                ondelete='cascade'),
        sa.PrimaryKeyConstraint('id')
    )
    op.add_column(u'users',
                  sa.Column('practitioner_id', sa.Integer(), nullable=True))
    op.create_foreign_key('user_practitioner_fkey', 'users', 'practitioners',
                          ['practitioner_id'], ['id'])


def downgrade():
    op.drop_constraint('user_practitioner_fkey', 'users', type_='foreignkey')
    op.drop_column(u'users', 'practitioner_id')
    op.drop_table('practitioners')
