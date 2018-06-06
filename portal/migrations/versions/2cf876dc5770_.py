"""empty message

Revision ID: 2cf876dc5770
Revises: 4638d0c1f06f
Create Date: 2016-03-25 15:50:55.866017

"""

# revision identifiers, used by Alembic.
revision = '2cf876dc5770'
down_revision = '4638d0c1f06f'

import sqlalchemy as sa
from alembic import op


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    stmt = """ALTER TABLE user_observations DROP CONSTRAINT
    user_observations_user_id_fkey, ADD CONSTRAINT
    user_observations_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE"""
    op.execute(stmt)
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    pass
    ### end Alembic commands ###
