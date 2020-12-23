"""Extend TOU types for EMPRO

Revision ID: 3c81fc76164c
Revises: 68a25f790d27
Create Date: 2020-12-22 12:45:27.743980

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c81fc76164c'
down_revision = '68a25f790d27'

old_tou_types = (
    'website terms of use', 'subject website consent',
    'stored website consent form', 'privacy policy')
new_tou_types = (
    'website terms of use', 'subject website consent',
    'stored website consent form', 'privacy policy',
    'EMPRO website terms of use')

old_type = sa.Enum(*old_tou_types, name='tou_types')
new_type = sa.Enum(*new_tou_types, name='tou_types')
tmp_type = sa.Enum(*new_tou_types, name='_tou_types')


def upgrade():
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE tou ALTER COLUMN type TYPE _tou_types'
        ' USING type::text::_tou_types')
    old_type.drop(op.get_bind(), checkfirst=False)

    # Create and convert to new type
    new_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE tou ALTER COLUMN type TYPE tou_types'
        ' USING type::text::tou_types')
    tmp_type.drop(op.get_bind(), checkfirst=False)


def downgrade():
    # Create old type for restoration - need tmp for storage
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE tou ALTER COLUMN type TYPE _tou_types'
        ' USING type::text::_tou_types')
    new_type.drop(op.get_bind(), checkfirst=False)

    old_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE tou ALTER COLUMN type TYPE tou_types'
        ' USING type::text::tou_types')
    tmp_type.drop(op.get_bind(), checkfirst=False)
