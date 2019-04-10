"""invalidate cache for any users with multiple consent rows

Revision ID: ede15dcea777
Revises: 687dd856dc5e
Create Date: 2019-04-10 14:47:34.398914

"""
from alembic import op
from sqlalchemy.orm import sessionmaker

# revision identifiers, used by Alembic.
revision = 'ede15dcea777'
down_revision = '687dd856dc5e'
Session = sessionmaker()


def upgrade():
    session = Session(bind=op.get_bind())
    query = (
        "delete from qb_timeline where user_id in ("
        "select distinct(user_id) from user_consents group by user_id "
        "having count(*) > 1)")
    session.execute(query)


def downgrade():
    # nothing needed
    pass
