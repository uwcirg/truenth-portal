from alembic import op
from sqlalchemy.orm import sessionmaker

from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.questionnaire_response import QuestionnaireResponse

"""empty message

Revision ID: 8ffec90e68a7
Revises: eaf653f36fc8
Create Date: 2017-09-18 15:59:01.535054

"""

# revision identifiers, used by Alembic.
revision = '8ffec90e68a7'
down_revision = 'eaf653f36fc8'

Session = sessionmaker()


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    for qnr in QuestionnaireResponse.query.all():
        if ("questionnaire" in qnr.document) and qnr.subject:
            qn_ref = qnr.document.get("questionnaire").get("reference")
            qn_name = qn_ref.split("/")[-1] if qn_ref else None
            qn = Questionnaire.query.filter_by(name=qn_name).first()

            qbd = QuestionnaireBank.most_current_qb(
                qnr.subject, as_of_date=qnr.authored)
            qb = qbd.questionnaire_bank
            ic = qbd.iteration
            if qb and qn and (qn.id in [qbq.questionnaire.id for qbq in
                                        qb.questionnaires]):
                ic = ic or 'NULL'
                session.execute(
                    'UPDATE questionnaire_responses SET '
                    'questionnaire_bank_id = {}, qb_iteration = {} WHERE '
                    'id = {}'.format(qb.id, ic, qnr.id))


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    session.execute('UPDATE questionnaire_responses SET '
                    'questionnaire_bank_id = NULL, qb_iteration = NULL')
