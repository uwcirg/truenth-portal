"""Add 'other' to qb classifications enum (and remove obsolete 'followup')

Revision ID: da6506c5899a
Revises: 9c6788e6db2f
Create Date: 2019-10-01 15:31:47.918164

"""
from alembic import op
import sqlalchemy as sa

from portal.models.questionnaire_bank import classification_types

# revision identifiers, used by Alembic.
revision = 'da6506c5899a'
down_revision = '9c6788e6db2f'

new_enum = sa.Enum(*classification_types, name='classification_enum')
tmp_enum = sa.Enum(*classification_types, name='_classification_enum')
old_types = [t for t in classification_types if t != 'other']
old_enum = sa.Enum(*old_types, name='classification_enum')


def upgrade():
    # Drop the default, as it's in the way
    op.execute(
        "ALTER TABLE questionnaire_banks ALTER classification DROP DEFAULT")

    # Need temp container during reassignment
    tmp_enum.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE questionnaire_banks ALTER COLUMN classification TYPE '
        '_classification_enum USING '
        'classification::text::_classification_enum')

    old_enum.drop(op.get_bind(), checkfirst=False)

    new_enum.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE questionnaire_banks ALTER COLUMN classification TYPE '
        'classification_enum USING classification::text::classification_enum')
    tmp_enum.drop(op.get_bind(), checkfirst=False)

    # restore default
    op.execute(
        "ALTER TABLE questionnaire_banks ALTER classification SET DEFAULT "
        "'baseline'::classification_enum")


def downgrade():

    # Drop any created with 'other'
    op.execute(
        "DELETE FROM questionnaire_banks WHERE classification = 'other'")
    # Drop the default, as it's in the way
    op.execute(
        "ALTER TABLE questionnaire_banks ALTER classification DROP DEFAULT")

    # Need temp container during reassignment
    tmp_enum.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE questionnaire_banks ALTER COLUMN classification TYPE '
        '_classification_enum USING '
        'classification::text::_classification_enum')

    new_enum.drop(op.get_bind(), checkfirst=False)

    old_enum.create(op.get_bind(), checkfirst=False)
    op.execute(
        'ALTER TABLE questionnaire_banks ALTER COLUMN classification TYPE '
        'classification_enum USING classification::text::classification_enum')
    tmp_enum.drop(op.get_bind(), checkfirst=False)

    # restore default
    op.execute(
        "ALTER TABLE questionnaire_banks ALTER classification SET DEFAULT "
        "'baseline'::classification_enum")
