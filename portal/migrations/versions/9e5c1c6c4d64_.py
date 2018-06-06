import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from portal.models.user_consent import UserConsent

"""empty message

Revision ID: 9e5c1c6c4d64
Revises: 8d187efaa505
Create Date: 2017-11-21 13:56:19.537803

"""

# revision identifiers, used by Alembic.
revision = '9e5c1c6c4d64'
down_revision = '8d187efaa505'

Session = sessionmaker()


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    status_enum = sa.Enum(
        'consented', 'suspended', 'deleted', name='status_enum')
    status_enum.create(op.get_bind(), checkfirst=False)

    op.add_column('user_consents',
                  sa.Column('status',
                            status_enum,
                            server_default='consented',
                            nullable=False))

    for uc in session.query(UserConsent).all():
        if uc.include_in_reports and not uc.send_reminders:
            uc.status = "suspended"
        elif ((not uc.staff_editable
                and not uc.include_in_reports
                and not uc.send_reminders) or uc.deleted_id):
            uc.status = "deleted"
        session.add(uc)
    session.commit()


def downgrade():
    op.drop_column('user_consents', 'status')
    sa.Enum(name='status_enum').drop(op.get_bind(), checkfirst=False)
