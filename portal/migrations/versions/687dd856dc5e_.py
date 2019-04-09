"""reset cache for all IRONMAN patients due to changes in PR #3108

Revision ID: 687dd856dc5e
Revises: 1e09e871fb65
Create Date: 2019-04-09 12:40:09.356697

"""
from alembic import op
import sqlalchemy as sa

from portal.database import db
from portal.models.organization import Organization, OrgTree
from portal.models.qb_timeline import QBT
from portal.models.user import User, patients_query

# revision identifiers, used by Alembic.
revision = '687dd856dc5e'
down_revision = '1e09e871fb65'


def upgrade():
    # Purge qb_timeline rows for all IRONMAN patients
    irnmn = Organization.query.filter(Organization.name == 'IRONMAN').first()
    if not irnmn:
        return

    admin = User.query.filter_by(email='__system__').first()
    irnmn_orgs = OrgTree().here_and_below_id(organization_id=irnmn.id)
    patients = patients_query(
        acting_user=admin, include_test_role=True,
        requested_orgs=irnmn_orgs).with_entities(User.id)
    # pat_ids = [p.id for p in patients]
    qbts = QBT.query.filter(QBT.user_id.in_(patients))
    qbts.delete(synchronize_session=False)
    db.session.commit()


def downgrade():
    # nothing needed
    pass
