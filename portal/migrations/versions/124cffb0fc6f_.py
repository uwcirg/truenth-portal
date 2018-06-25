from alembic import op
import sqlalchemy as sa

"""Add `url_authenticated_and_verified` to encounter.auth_method enum

Revision ID: 124cffb0fc6f
Revises: 40b223faa7d4
Create Date: 2018-01-29 16:35:25.374574

"""

# revision identifiers, used by Alembic.
revision = '124cffb0fc6f'
down_revision = '40b223faa7d4'

old_auth_method_types = (
    'password_authenticated', 'url_authenticated', 'staff_authenticated',
    'staff_handed_to_patient', 'service_token_authenticated',
    )
new_auth_method_types = (
    'password_authenticated', 'url_authenticated', 'staff_authenticated',
    'staff_handed_to_patient', 'service_token_authenticated',
    'url_authenticated_and_verified',
    )

old_type = sa.Enum(*old_auth_method_types, name='auth_methods')
new_type = sa.Enum(*new_auth_method_types, name='auth_methods')
tmp_type = sa.Enum(*new_auth_method_types, name='_auth_methods')


def upgrade():
    # Create tmp enum to hold, convert and drop the old
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE encounters ALTER COLUMN auth_method TYPE _auth_methods'
        ' USING auth_method::text::_auth_methods')
    old_type.drop(op.get_bind(), checkfirst=False)

    # Create and convert to new type
    new_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE encounters ALTER COLUMN auth_method TYPE auth_methods'
        ' USING auth_method::text::auth_methods')
    tmp_type.drop(op.get_bind(), checkfirst=False)


def downgrade():
    # Force any created into best available old value
    op.execute(
        "UPDATE encounters SET auth_method = 'url_authenticated' "
        "WHERE auth_method = 'url_authenticated_and_verified'")

    # Create old type for restoration - need tmp for storage
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE encounters ALTER COLUMN auth_method TYPE _auth_methods'
        ' USING auth_method::text::_auth_methods')
    new_type.drop(op.get_bind(), checkfirst=False)

    old_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE encounters ALTER COLUMN auth_method TYPE auth_methods'
        ' USING auth_method::text::auth_methods')
    tmp_type.drop(op.get_bind(), checkfirst=False)
