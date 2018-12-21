from alembic import op


"""rename DSTU2 Questionnaire.group to item

Revision ID: e5aec2aebe7e
Revises: 883fd1095361
Create Date: 2018-11-21 11:20:32.766295

"""

# revision identifiers, used by Alembic.
revision = 'e5aec2aebe7e'
down_revision = '883fd1095361'


def upgrade():
    op.alter_column(
        'questionnaires',
        column_name='group',
        new_column_name='item',
    )


def downgrade():
    op.alter_column(
        'questionnaires',
        column_name='item',
        new_column_name='group',
    )
