"""Force cache renewal for QNRs where user's consent changed

Revision ID: a97e02e09733
Revises: 458e56eedb92
Create Date: 2019-06-06 13:46:13.177232

"""
from alembic import op
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = 'a97e02e09733'
down_revision = '458e56eedb92'


def upgrade():
    # Locate users with both:
    #   - multiple user_consents (beyond one and then a withdrawn)
    #   - submitted QNRs
    conn = op.get_bind()
    query = (
        "SELECT DISTINCT(subject_id) FROM questionnaire_responses WHERE"
        " subject_id in (SELECT user_id FROM user_consents WHERE"
        " status != 'suspended' GROUP BY user_id HAVING count(*) > 1)")

    qualifying_user_ids = [
        row.subject_id for row in conn.execute(query).fetchall()]
    print("Found {} users needing refresh".format(len(qualifying_user_ids)))

    # Purge the QNR -> QB relationships
    query = (
        "UPDATE questionnaire_responses SET questionnaire_bank_id=NULL,"
        " qb_iteration=NULL WHERE subject_id IN :subject_ids")
    conn.execute(text(query), subject_ids=tuple(qualifying_user_ids))

    # Purge the QBTimeline rows (cached data)
    query = "DELETE FROM qb_timeline WHERE user_id IN :user_ids"
    conn.execute(text(query), user_ids=tuple(qualifying_user_ids))


def downgrade():
    # no downgrade for this migration
    pass
