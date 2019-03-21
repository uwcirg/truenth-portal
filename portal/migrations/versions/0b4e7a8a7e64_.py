"""Purge cached timeline for withdrawn patients

Revision ID: 0b4e7a8a7e64
Revises: 1d84237ed07c
Create Date: 2019-03-18 16:01:13.361506

"""
import sqlalchemy as sa

from portal.database import db
from portal.models.user import User, UserRoles
from portal.models.user_consent import UserConsent
from portal.models.qb_timeline import QBT
from portal.models.role import Role, ROLE


# revision identifiers, used by Alembic.
revision = '0b4e7a8a7e64'
down_revision = '1d84237ed07c'

def purge_suspended_patients_qbs():
    suspended = User.query.join(UserRoles).join(
        Role).join(UserConsent).filter(sa.and_(
        Role.id == UserRoles.role_id, UserRoles.user_id == User.id,
        Role.name == ROLE.PATIENT.value)).filter(
        UserConsent.status == 'suspended').with_entities(User.id)
    qbts = QBT.query.filter(QBT.user_id.in_(suspended))
    qbts.delete(synchronize_session=False)
    db.session.commit()


def upgrade():
    # Fix for TN-1871, modifies QB Timeline / Status for withdrawn
    # patients.  Remove existing qb_timeline rows for this set of
    # patients.
    purge_suspended_patients_qbs()


def downgrade():
    # same process both directions - as downgrade would imply returning
    # to old process and the cached data would be incorrect
    purge_suspended_patients_qbs()
