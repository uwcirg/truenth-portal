import sqlalchemy as sa
from alembic import op

"""empty message

Revision ID: d0b40bc8d7e6
Revises: 8ffec90e68a7
Create Date: 2017-09-20 05:59:45.168324

"""

# revision identifiers, used by Alembic.
revision = 'd0b40bc8d7e6'
down_revision = '8ffec90e68a7'


def upgrade():
    # Work around site_persistence fragility.  Replace a couple names
    # as delete and recreate on these fails due to FK constraints
    op.execute("UPDATE questionnaire_banks SET name = 'IRONMAN_baseline' "
               "  WHERE name = 'IRONMAN baseline'")
    op.execute("UPDATE questionnaire_banks SET name = 'CRV_baseline' "
               "  WHERE name = 'CRV baseline'")


def downgrade():
    op.execute("UPDATE questionnaire_banks SET name = 'IRONMAN baseline' "
               "  WHERE name = 'IRONMAN_baseline'")
    op.execute("UPDATE questionnaire_banks SET name = 'CRV baseline' "
               "  WHERE name = 'CRV_baseline'")
