"""Make Questionnaire model more FHIR like

Revision ID: df7f10d6fd60
Revises: 5aeadb11e97b
Create Date: 2018-03-21 16:25:10.457911

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision = 'df7f10d6fd60'
down_revision = '5aeadb11e97b'


status_types = ENUM(
    'draft', 'published', 'retired', name='questionnaire_status_enum', create_type=False)


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    status_types.create(op.get_bind(), checkfirst=False)
    op.add_column(
        'questionnaires', sa.Column(
            'group', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        'questionnaires', sa.Column(
            'status', status_types,
            server_default='draft', nullable=False))
    op.drop_column('questionnaires', 'document')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        'questionnaires', sa.Column(
            'document', postgresql.JSONB(
                astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.drop_column('questionnaires', 'status')
    op.drop_column('questionnaires', 'group')
    # ### end Alembic commands ###
