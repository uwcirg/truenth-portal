"""nop revision filler in place of IRONN-324 fix

Revision ID: 138e7a0feffc
Revises: c4f8a2b91d07
Create Date: 2026-09-15 17:14:04.117364

"""
# revision identifiers, used by Alembic.
revision = '138e7a0feffc'
down_revision = 'c4f8a2b91d07'


def upgrade():
    # no op migration; necessary to keep revision system happy after applying a
    # migration of the same number, then reverting the code.
    pass


def downgrade():
    # no reasonable downgrade for this migration
    pass
