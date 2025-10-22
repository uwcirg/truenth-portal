"""TN-3354 Contact Us enquiry type update

Revision ID: 71da0b18ec5f
Revises: 4f5daa2b48db
Create Date: 2025-10-21 13:33:11.564463

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '71da0b18ec5f'
down_revision = '4f5daa2b48db'


def upgrade():
    # The list of `enquiry types` available in the contact us form, come
    # from organizations with a defined email address.  Remove the email
    # from TNGR as it is no longer desired in the list (see TN-3354)
    sql = sa.sql.text("""UPDATE organizations SET email = '' WHERE name = :name""")
    conn = op.get_bind()
    conn.execute(sql, {'name': "TrueNTH Global Registry"})


def downgrade():
    # Reverse the above
    sql = sa.sql.text("""UPDATE organizations SET email = :email WHERE name = :name""")
    conn = op.get_bind()
    conn.execute(sql, {'email': "contact.eproms@truenth.org", 'name': "TrueNTH Global Registry"})
