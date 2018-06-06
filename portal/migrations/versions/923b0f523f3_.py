"""empty message

Revision ID: 923b0f523f3
Revises: 32061cd3a2a2
Create Date: 2015-06-22 16:49:20.885279

"""

# revision identifiers, used by Alembic.
revision = '923b0f523f3'
down_revision = '32061cd3a2a2'

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('assessment')
    op.create_index(op.f('ix_grants_code'), 'grants', ['code'], unique=False)
    op.drop_index('ix_grant_code', table_name='grants')
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_index('ix_grant_code', 'grants', ['code'], unique=False)
    op.drop_index(op.f('ix_grants_code'), table_name='grants')
    op.create_table('assessment',
                    sa.Column('id', sa.INTEGER(), nullable=False),
                    sa.Column('user_id', sa.INTEGER(),
                              autoincrement=False, nullable=True),
                    sa.Column('assessment_type', sa.VARCHAR(length=40),
                              autoincrement=False, nullable=True),
                    sa.Column('taken', postgresql.TIMESTAMP(),
                              autoincrement=False, nullable=True),
                    sa.ForeignKeyConstraint(
                        ['user_id'], [u'users.id'], name=u'assessment_user_id_fkey'),
                    sa.PrimaryKeyConstraint('id', name=u'assessment_pkey')
                    )
    ### end Alembic commands ###
