"""IRONN-225 update adherence data for expired EMPRO users

Revision ID: 66368e673005
Revises: d1f3ed8d16ef
Create Date: 2023-12-11 16:56:10.427854

"""
from alembic import op
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker


# revision identifiers, used by Alembic.
revision = '66368e673005'
down_revision = 'd1f3ed8d16ef'

Session = sessionmaker()


def upgrade():
    # IRONN-225 noted expired EMPRO users adherence data showed
    # `not yet available`.  Code corrected, need to force renewal
    # for those affected.

    bind = op.get_bind()
    session = Session(bind=bind)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    patient_ids = []
    # get list of non-deleted users with a 12th month expiration
    # that has already passed.  (12 = baseline + zero-index 10)
    for patient_id in session.execute(
            "SELECT DISTINCT(user_id) FROM qb_timeline JOIN users"
            " ON users.id = user_id WHERE deleted_id IS NULL"
            " AND research_study_id = 1 AND qb_iteration = 10"
            f" AND status = 'expired' AND at < '{now}'"):
        patient_ids.append(patient_id[0])

    # purge their respective rows from adherence cache, IFF status
    # shows IRONN-225 symptom.
    rs_visit = "1:Month 12"
    for patient_id in patient_ids:
        status = session.execute(
            "SELECT data->>'status' FROM adherence_data WHERE"
            f" patient_id = {patient_id} AND"
            f" rs_id_visit = '{rs_visit}'"
        ).first()
        if status and status[0] != "Not Yet Available":
            continue

        # purge the user's EMPRO adherence rows to force refresh
        session.execute(
            "DELETE FROM adherence_data WHERE"
            f" patient_id = {patient_id} AND"
            f" rs_id_visit like '1:%'"
        )


def downgrade():
    # No reasonable downgrade
    pass

