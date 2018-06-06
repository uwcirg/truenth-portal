from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

"""empty message

Revision ID: 40b223faa7d4
Revises: 2126386257ad
Create Date: 2018-01-18 14:58:36.140440

"""

# revision identifiers, used by Alembic.
revision = '40b223faa7d4'
down_revision = '2126386257ad'


Session = sessionmaker()


def update_job_name(session, old, new):
    session.execute("UPDATE scheduled_jobs SET name = '{}' "
                    "WHERE name = '{}'".format(new, old))


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    update_job_name(session,
                    'Website consent update notification',
                    "Subject website consent update notification "
                    "(run this ONLY AFTER "
                    "''Deactivate subject website consent agreements'' job)")

    update_job_name(session,
                    'PrivacyPolicy update notification',
                    'Privacy policy update notification')

    update_job_name(session,
                    'Terms update notification',
                    'Website terms update notification')


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    update_job_name(session,
                    "Subject website consent update notification "
                    "(run this ONLY AFTER "
                    "''Deactivate subject website consent agreements'' job)",
                    'Website consent update notification')

    update_job_name(session,
                    'Privacy policy update notification',
                    'PrivacyPolicy update notification')

    update_job_name(session,
                    'Website terms update notification',
                    'Terms update notification')
