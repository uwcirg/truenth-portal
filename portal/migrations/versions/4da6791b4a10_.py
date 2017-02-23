"""empty message

Revision ID: 4da6791b4a10
Revises: b1d13b4b175a
Create Date: 2016-12-30 13:19:38.079888

"""

# revision identifiers, used by Alembic.
revision = '4da6791b4a10'
down_revision = 'b1d13b4b175a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('questionnaire_responses', column_name='user_id', new_column_name='subject_id')

def downgrade():
    op.alter_column('questionnaire_responses', column_name='subject_id', new_column_name='user_id')
