"""Delete Zulu locale from non-test organizations

Revision ID: 49d13048e7a7
Revises: ebb5fee8122b
Create Date: 2021-05-19 19:56:40.131569

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '49d13048e7a7'
down_revision = 'ebb5fee8122b'


def upgrade():
    # delete Zulu locale
    op.execute("delete from organization_locales where id in (select ol.id from organizations o join organization_locales ol on o.id=ol.organization_id join codings c on ol.coding_id=c.id where code='zu_ZA' and o.name not like '%Test%')")


def downgrade():
    pass
