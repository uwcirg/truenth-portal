"""remove Zulu locale

Revision ID: d1f3ed8d16ef
Revises: 80c3b1e96c45
Create Date: 2023-12-05 14:09:10.442328

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1f3ed8d16ef'
down_revision = '80c3b1e96c45'


def upgrade():
    # switch user's locale to GB english for any user with Zulu
    op.execute(
        "update users set locale_id = "
        "(select codeable_concept_id from codeable_concept_codings where coding_id in "
        "(select id from codings where code = 'en_GB')) where locale_id = "
        "(select codeable_concept_id from codeable_concept_codings where coding_id in "
        "(select id from codings where code = 'zu_ZA'))"
    )

    # remove the Zulu codeable_concept
    op.execute(
        "delete from codeable_concept_codings where coding_id in "
        "(select id from codings where code = 'zu_ZA')")

    # remove Zulu from any orgs
    op.execute(
        "delete from organization_locales where coding_id = (select id from codings where code = 'zu_ZA')"
    )

    # remove the Zulu coding
    op.execute("delete from codings where code = 'zu_ZA'")


def downgrade():
    # no restoration path
    pass
