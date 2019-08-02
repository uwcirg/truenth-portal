"""flush qb_timeline cache for all suspended workers

Revision ID: 2e1421ac841a
Revises: ede15dcea777
Create Date: 2019-04-16 17:08:12.928760

"""
import sqlalchemy as sa

from portal.database import db
from portal.models.qb_timeline import QBT
from portal.models.role import ROLE, Role
from portal.models.user import User, UserRoles
from portal.models.user_consent import UserConsent


def purge_suspended_patients_qbs():
    suspended = User.query.join(UserRoles).join(Role).join(
        UserConsent).filter(sa.and_(
            Role.id == UserRoles.role_id, UserRoles.user_id == User.id,
            Role.name == ROLE.PATIENT.value)).filter(
        UserConsent.status == 'suspended').with_entities(User.id)
    qbts = QBT.query.filter(QBT.user_id.in_(suspended))
    qbts.delete(synchronize_session=False)
    db.session.commit()


# revision identifiers, used by Alembic.
revision = '2e1421ac841a'
down_revision = 'ede15dcea777'


def upgrade():
    purge_suspended_patients_qbs()


def downgrade():
    purge_suspended_patients_qbs()
