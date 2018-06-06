"""empty message

Revision ID: c13728c5e64e
Revises: b1d13b4b175a
Create Date: 2016-12-29 08:56:03.779772

"""

# revision identifiers, used by Alembic.
revision = 'c13728c5e64e'
down_revision = 'b1d13b4b175a'

import sqlalchemy as sa
from alembic import op


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column(
        'deceased_id', sa.Integer(), nullable=True))
    op.create_foreign_key('user_deceased_audit_id_fk', 'users', 'audit', [
                          'deceased_id'], ['id'], use_alter=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('user_deceased_audit_id_fk',
                       'users', type_='foreignkey')
    op.drop_column('users', 'deceased_id')
    # ### end Alembic commands ###
