from alembic import op
from datetime import timedelta
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.models.user import User, UserRoles
from portal.models.role import Role

from portal.models.audit import Audit
from portal.models.user_consent import UserConsent

"""Correct user_consent acceptance_date as default arg wasn't updating

Revision ID: 883fd1095361
Revises: 67c2bea62313
Create Date: 2018-10-11 12:48:33.980877

"""
# revision identifiers, used by Alembic.
revision = '883fd1095361'
down_revision = '67c2bea62313'
Session = sessionmaker()


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    admin = User.query.filter_by(email='bob25mary@gmail.com').first()
    admin = admin or User.query.join(
        UserRoles).join(Role).filter(
        sa.and_(
            Role.id == UserRoles.role_id, UserRoles.user_id == User.id,
            Role.name == 'admin')).first()
    admin_id = admin.id

    query = session.query(UserConsent).join(
        Audit, UserConsent.audit_id == Audit.id).with_entities(
        UserConsent, Audit.timestamp)

    eligible_uc_ids = {}
    for uc, timestamp in query:
        if uc.acceptance_date.microsecond != 0:
            # skip the honest ones, that differ by milliseconds
            if timestamp - uc.acceptance_date < timedelta(seconds=5):
                continue
            if timestamp - uc.acceptance_date > timedelta(days=8):
                raise ValueError(
                    "too big of a jump - please review {} {} {}".format(
                        uc.user_id, timestamp, uc.acceptance_date))
            eligible_uc_ids[uc.id] = (
                uc.acceptance_date, timestamp.replace(microsecond=0))

    # now update each in eligible list outside of initial query
    for uc_id, dates in eligible_uc_ids.items():
        old_acceptance_date, new_acceptance_date = dates
        msg = "Correct stale default acceptance_date {} to {}".format(
            old_acceptance_date, new_acceptance_date)
        uc = session.query(UserConsent).get(uc_id)
        audit = Audit(
            user_id=admin_id, subject_id=uc.user_id, context='consent',
            comment=msg)
        uc.audit = audit
        uc.acceptance_date = new_acceptance_date

    session.commit()


def downgrade():
    # no value in undoing that mess
    pass
