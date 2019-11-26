"""Fixup answers to dsp_factors.1

Revision ID: 908731b85112
Revises: 677b8b841cb3
Create Date: 2019-11-21 21:34:41.092472

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.models.questionnaire_response import QuestionnaireResponse

# revision identifiers, used by Alembic.
revision = '908731b85112'
down_revision = '677b8b841cb3'


Session = sessionmaker()

factors_q1_code_map = {
    "No influence": "dsp_factors.1.1",
    "A little influence": "dsp_factors.1.2",
    "Some influence": "dsp_factors.1.3",
    "A lot of influence": "dsp_factors.1.4",
}


def fixup_dsp_factors(questionnaire_response_json):
    """Fix erroneously created responses"""
    # exit early if preconditions not met
    # first question is type choice
    # expect 1 answer (valueCoding and legacy valueString)
    if len(questionnaire_response_json['group']['question'][0]['answer']) <= 2:
        return questionnaire_response_json

    qnr_json_copy = dict(questionnaire_response_json)
    target_question = qnr_json_copy['group']['question'][0]
    # broken set of answers to first question
    empty_answer, selected_answer, null_answer = target_question['answer']

    corrected_answers = (
        {'valueString': selected_answer['valueString']},
        # lookup answer code from valueString
        {'valueCoding': factors_q1_code_map[selected_answer['valueString']]},
    )

    target_question['answer'] = corrected_answers
    return qnr_json_copy


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    session = Session(bind=op.get_bind())

    instrument_id = 'dsp_factors'
    questionnaire_responses = session.query(QuestionnaireResponse).filter(
        QuestionnaireResponse.document[
            ("questionnaire", "reference")
        ].astext.endswith(instrument_id)
    ).order_by(QuestionnaireResponse.id)

    for qnr in questionnaire_responses:
        qnr_json = fixup_dsp_factors(qnr.document)
        # "Reset" QNR to save updated data
        # Todo: fix JSONB mutation detection
        # See https://bugs.launchpad.net/fuel/+bug/1482658
        qnr.document = {}
        session.add(qnr)
        session.commit()

        qnr.document = qnr_json
        session.add(qnr)
        session.commit()
        assert qnr.document
        print("Processed QNR: %d" % qnr.id)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
