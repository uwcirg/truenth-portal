"""Withdrawn patient timeline cleanup

Revision ID: 1a84c56e6abc
Revises: f46c82c33c5c
Create Date: 2021-03-18 14:56:43.257737

"""
from alembic import op
from sqlalchemy.sql import text
from portal.models.qb_timeline import invalidate_users_QBT

# revision identifiers, used by Alembic.
revision = '1a84c56e6abc'
down_revision = 'f46c82c33c5c'


def upgrade():
    """A small handful of patients have an invalid timeline withdrawn row

    When a user is withdrawn, the timeline mechanism expects to find either
    zero timeline rows (if they withdrew before they got started) or at
    least the `due` event matching the visit with the user's `withdrawn`
    event.  This migration seeks out the few noticed on truenth-test,
    as others may exist elsewhere, to fix the invalid state.

    """
    conn = op.get_bind()

    withdrawn_rows = conn.execute(
        "SELECT user_id, qb_id, qb_iteration FROM qb_timeline"
        " WHERE status = 'withdrawn'").fetchall()

    for user_id, qb_id, qb_iteration in withdrawn_rows:
        # If there's a similar row for the user with a `due` status
        # all is well.  Otherwise, said user needs an update
        matching_due = conn.execute(text(
            "SELECT id FROM qb_timeline WHERE user_id=:user_id"
            " AND qb_id=:qb_id AND qb_iteration=:qb_iteration"
            " AND status='due'"), user_id=user_id, qb_id=qb_id,
            qb_iteration=qb_iteration).fetchall()
        if len(matching_due) == 1:
            continue
        print(f"found problem user: {user_id}")
        invalidate_users_QBT(user_id=user_id, research_study_id=0)


def downgrade():
    pass
