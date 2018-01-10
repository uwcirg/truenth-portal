from __future__ import print_function
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from StringIO import StringIO
import sys

from portal.dict_tools import dict_match
from portal.models.fhir import QuestionnaireResponse

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
        query = (
            "select subject_id, questionnaire_bank_id, "
            " document->'questionnaire'->>'reference' as reference "
            "from questionnaire_responses "
            "group by subject_id, questionnaire_bank_id, reference "
            "having count(*) > 1"
        )

        for subject_id, qb_id, reference in session.execute(query):
            yield subject_id, reference

    def keep_one(subject_id, reference):
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
                report = StringIO()
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

    for subject_id, reference in needs_attention():
        keep_one(subject_id, reference)


def downgrade():
    # no point in replicating that mess
    pass
