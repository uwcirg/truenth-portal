from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.models.questionnaire_bank import QuestionnaireBank


"""empty message

Revision ID: ffc71c89282f
Revises: 9e5c1c6c4d64
Create Date: 2017-12-07 14:54:47.576283

"""

# revision identifiers, used by Alembic.
revision = 'ffc71c89282f'
down_revision = '9e5c1c6c4d64'

Session = sessionmaker()


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    qb = session.query(QuestionnaireBank).filter_by(
        name='IRONMAN_indefinite').first()

    if qb:
        session.execute("UPDATE questionnaire_responses "
                        "SET questionnaire_bank_id = {}"
                        "WHERE document->'questionnaire'->>'reference' "
                        "LIKE '%{}'".format(qb.id, '/irondemog'))


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    session.execute("UPDATE questionnaire_responses "
                    "SET questionnaire_bank_id = NULL "
                    "WHERE document->'questionnaire'->>'reference' "
                    "LIKE '%{}'".format('/irondemog'))
