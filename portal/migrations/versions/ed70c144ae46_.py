"""Eliminate internal identifiers

Revision ID: ed70c144ae46
Revises: 3da0caa42c62
Create Date: 2018-05-02 17:39:24.558043

"""
from alembic import op
from sqlalchemy import text

from portal.models.user import internal_identifier_systems

# revision identifiers, used by Alembic.
revision = 'ed70c144ae46'
down_revision = '3da0caa42c62'


def upgrade():
    conn = op.get_bind()

    # Internal identifiers don't belong in the database - they're at best
    # duplicate data, and at worse, conflicting.
    identifiers = text(
        "SELECT id FROM identifiers WHERE system IN :internal_systems")
    bad_ids = [i[0] for i in conn.execute(
            identifiers,
            internal_systems=tuple(internal_identifier_systems))]
    remove_uis = text(
        "DELETE FROM user_identifiers WHERE identifier_id IN :bad_ids")
    conn.execute(remove_uis, bad_ids=tuple(bad_ids))
    remove_ids = text("DELETE FROM identifiers WHERE id IN :bad_ids")
    conn.execute(remove_ids, bad_ids=tuple(bad_ids))


def downgrade():
    # no downgrade step - bogus data need not come back
    pass
