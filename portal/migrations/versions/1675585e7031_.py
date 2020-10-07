"""Remove obsolete user_intervention rows housing assessment engine HTML

Revision ID: 1675585e7031
Revises: 6395e14d5ee5
Create Date: 2020-10-07 12:45:57.880998

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1675585e7031'
down_revision = '6395e14d5ee5'


def upgrade():
    """Assessment Engine has its own view, no longer pushing HTMl into db

    Remove obsolete user_intervention rows.
    """
    op.execute(
        "delete from user_interventions using interventions"
        " where intervention_id = interventions.id"
        " and interventions.name = 'assessment_engine'")


def downgrade():
    # They're gone - restore db if necessary.
    pass
