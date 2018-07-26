from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.models.fhir import QuestionnaireResponse

"""empty message

Revision ID: 8efa45d83a3b
Revises: b4dcf331317e
Create Date: 2018-07-23 12:58:12.567890

"""

# revision identifiers, used by Alembic.
revision = '8efa45d83a3b'
down_revision = 'b4dcf331317e'

Session = sessionmaker()


def increment_linkId(linkId):
    instrument_id, question_index = linkId.split('.')

    return "{instrument_id}.{question_index}".format(
        instrument_id=instrument_id,
        question_index=int(question_index)+1,
    )


def increment_code(code):
    instrument_id, question_index, option_index = code.split('.')

    return "{instrument_id}.{question_index}.{option_index}".format(
        instrument_id=instrument_id,
        question_index=int(question_index)+1,
        option_index=option_index,
    )


def reindex_questions(questionnaire_response_json):
    """Modify QuestionnaireResponse codes in-place"""
    for question in questionnaire_response_json['group']['question']:
        question['linkId'] = increment_linkId(question['linkId'])

        for answer in question['answer']:
            coding_answer_data = answer.get('valueCoding')
            if not coding_answer_data:
                continue

            coding_answer_data['code'] = increment_code(coding_answer_data['code'])

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    # ### end Alembic commands ###
    instrument_id = 'irondemog_v3'

    questionnaire_responses = questionnaire_responses.filter(
        QuestionnaireResponse.document[
            ("questionnaire", "reference")
        ].astext.endswith(instrument_id)
    ).order_by(QuestionnaireResponse.id)

    for qnr in questionnaire_responses:
        reindex_questions(qnr.document)
        session.add(qnr)
    session.commit()


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
