from __future__ import print_function

from io import BytesIO
import sys

from alembic import op
from flask import current_app
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.dict_tools import dict_match
from portal.models.questionnaire_response import QuestionnaireResponse

"""empty message

Revision ID: 84d8d857c2c6
Revises: ffc71c89282f
Create Date: 2017-12-13 16:30:25.578520

"""

# revision identifiers, used by Alembic.
revision = '84d8d857c2c6'
down_revision = 'ffc71c89282f'

Session = sessionmaker()


def upgrade():
    # eliminate duplicate questionnaires created by a bug
    # with stale sessions on AE
    session = Session(bind=op.get_bind())

    def needs_attention():
        # TNUSA - QNRs do not necessarily have questionnaire_bank_id
        if current_app.config.get('GIL'):
            print("TNUSA detected, ignoring questionnaire_bank_id")

            # find QNRs of the same type completed within 1 minute of each other
            # https://stackoverflow.com/questions/4342370/27631673#27631673
            query = (
                "SELECT string_agg(id::text, ', ') AS agg_qnr_ids, subject_id, "
                "to_timestamp(floor((extract('epoch' from authored) / 60 )) * 60) "
                "AT TIME ZONE 'UTC' as interval_alias, "
                "document->'questionnaire'->>'reference' as reference "
                "FROM questionnaire_responses "
                "GROUP BY interval_alias, subject_id, reference having count(*) > 1 "
            )

            for agg_qnr_ids, subject_id, interval_alias, reference in session.execute(query):
                yield {'qnr_ids': agg_qnr_ids.split(', ')}

        # ePROMs - there should only be 1 QNR of a given type, for a QB
        else:
            print("ePROMs detected, finding dupes by questionnaire_bank_id")
            query = (
                "select subject_id, "
                " document->'questionnaire'->>'reference' as reference "
                "from questionnaire_responses "
                "group by subject_id, questionnaire_bank_id, reference "
                "having count(*) > 1"
            )

            for subject_id, reference in session.execute(query):
                yield {
                    'subject_id': subject_id,
                    'reference': reference,
                }

    def keep_one(subject_id=None, reference=None, qnr_ids=None):
        if qnr_ids is not None:
            items = session.query(QuestionnaireResponse).filter(
                QuestionnaireResponse.id.in_(qnr_ids)
            ).order_by(QuestionnaireResponse.id)
        else:
            items = session.query(QuestionnaireResponse).filter(
                QuestionnaireResponse.subject_id == subject_id).filter(
                QuestionnaireResponse.document[
                    ("questionnaire", "reference")
                ].astext == reference).order_by(QuestionnaireResponse.id)

        keeper = None
        for i in items:
            if keeper is None:
                keeper = i
                print("Keep {}".format(keeper))
                continue
            # Confirm results are the same
            if keeper.document != i.document:
                report = BytesIO()
                dict_match(keeper.document, i.document, report)
                print(report.getvalue())
                print("ERROR different docs; skipping QNRs {} and {}".format(
                    keeper.id, i.id), file=sys.stderr)
                continue
            print("  deleting {}".format(i))
            # direct delete of obj breaks due to fk w/ encounter
            session.execute(sa.text(
                "DELETE FROM questionnaire_responses WHERE ID = :ID").params(
                ID=i.id))

    for data in needs_attention():
        keep_one(**data)


def downgrade():
    # no point in replicating that mess
    pass
