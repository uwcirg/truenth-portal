"""IRONN-324 correct visit month on clinician qnr

Revision ID: 138e7a0feffc
Revises: c4f8a2b91d07
Create Date: 2026-09-15 17:14:04.117364

"""
from alembic import op
from sqlalchemy.orm import sessionmaker

from portal.models.questionnaire_response import QuestionnaireResponse
from portal.models.research_data import add_questionnaire_response

# revision identifiers, used by Alembic.
revision = '138e7a0feffc'
down_revision = 'c4f8a2b91d07'

Session = sessionmaker()


def upgrade():
    # The clinician response QNR timing can't be simply calculated from
    # the EMPRO schedule, as the patient may have submitted near the end
    # of the valid visit period, and the clinician's response may be a
    # few days later.  Remove and recalculate all research_data rows
    # for this particular instrument
    bind = op.get_bind()
    session = Session(bind=bind)

    qnr_ids = {}
    for row in session.execute(
            """SELECT questionnaire_response_id, data->>'timepoint' FROM research_data WHERE instrument = 'ironman_ss_post_tx'"""):
        qnr_ids[row[0]] = row[1]


    session.execute(
        """DELETE FROM research_data WHERE instrument = 'ironman_ss_post_tx'""")
    for qnr_id, old_visit in qnr_ids.items():
        print(f"reprocess research_data.questionnaire_response_id {qnr_id} with visit {old_visit}")
        continue  # can't get the session management to work, Alembic hangs on second iteration
        # rely on the `cache_research_data_task` job to re-evaluate the research data


def downgrade():
    # no reasonable downgrade for this migration
    pass
