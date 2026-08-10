"""Purge EMPRO data (TN-3367)

Revision ID: b5b6f6753c9b
Revises: c4f8a2b91d07
Create Date: 2026-08-03 13:18:54.677341

"""
from alembic import op
import logging
from sqlalchemy import text

from portal.models.research_study import EMPRO_RS_ID

# revision identifiers, used by Alembic.
revision = 'b5b6f6753c9b'
down_revision = 'c4f8a2b91d07'

logger = logging.getLogger("alembic")
#logger.setLevel(logging.DEBUG)
#logger.addHandler(logging.StreamHandler())

def upgrade():
    conn = op.get_bind()
    # A number of significant steps.  NB, no supported downgrade
    # once done, only "undo" would be a database restoration.

    assert(EMPRO_RS_ID == 1)
    logger.info(f"PURGING EMPRO DATA")

    # 1. Delete all EMPRO consents.
    result = conn.execute("DELETE FROM user_consents WHERE research_study_id = 1")
    logger.info(f"DELETE {result.rowcount} user_consent rows")

    #2. Delete all EMPRO QuestionnaireResponses (and everything with a foreign key attachment)
    result = conn.execute("DELETE FROM research_data WHERE research_study_id = 1")
    logger.info(f"DELETE {result.rowcount} research_data rows")
    result = conn.execute(
        text(
            "DELETE FROM adherence_data WHERE rs_id_visit like :search_pattern"),
            {'search_pattern': '1:%'})
    logger.info(f"DELETE {result.rowcount} adherence_data rows")
    result = conn.execute("DELETE FROM trigger_states")
    logger.info(f"DELETE {result.rowcount} trigger_states rows")

    query = text(
        "DELETE FROM questionnaire_responses WHERE "
        "  document->'questionnaire'->>'reference' like :search_pattern")
    result = conn.execute(query, {'search_pattern': '%ironman_ss%'})
    logger.info(f"DELETE {result.rowcount} questionnaire_responses rows")

    #3. Purge the EMPRO Questionnaires.
    query = text(
        "DELETE FROM questionnaires WHERE id IN "
        "  (SELECT questionnaire_id FROM questionnaire_identifiers WHERE identifier_id IN "
        "  (SELECT id FROM identifiers WHERE value like :search_pattern))"
    )
    result = conn.execute(query, {'search_pattern': 'ironman_ss%'})
    logger.info(f"DELETE {result.rowcount} questionnaires rows")

    #4. Purge the EMPRO QuestionnaireBanks
    #   must first purge related Communications and CommunicationRequests.
    query = text(
        "DELETE FROM communications WHERE communication_request_id IN "
        "  (SELECT id from communication_requests WHERE questionnaire_bank_id IN "
        "  (SELECT id FROM questionnaire_banks WHERE name like :search_pattern))")
    result = conn.execute(query, {'search_pattern': 'ironman_ss%'})
    logger.info(f"DELETE {result.rowcount} communications rows")

    query = text(
        "DELETE from communication_requests WHERE questionnaire_bank_id IN "
        "  (SELECT id FROM questionnaire_banks WHERE name like :search_pattern)")
    result = conn.execute(query, {'search_pattern': 'ironman_ss%'})
    logger.info(f"DELETE {result.rowcount} communication_requests rows")

    query = text(
        "DELETE FROM questionnaire_banks WHERE name like :search_pattern"
    )
    result = conn.execute(query, {'search_pattern': 'ironman_ss%'})
    logger.info(f"DELETE {result.rowcount} questionnaire_banks rows")

    # Unwind the SDC Observations from EMPRO

    query = text(
        "DELETE FROM observations WHERE codeable_concept_id IN "
        "  (SELECT codeable_concept_id FROM codeable_concept_codings WHERE coding_id IN "
        "  (SELECT id FROM codings WHERE system = :search_pattern))"
    )
    result = conn.execute(query, {'search_pattern': 'http://us.truenth.org/observation'})
    #observation_ids = [row[0] for row in result.fetchall()]
    logger.info(f"DELETE {result.rowcount} observations rows")

    query = text(
        "DELETE FROM codeable_concept_codings WHERE coding_id IN "
        "  (SELECT id FROM codings WHERE system = :search_pattern)"
    )
    result = conn.execute(query, {'search_pattern': 'http://us.truenth.org/observation'})
    logger.info(f"DELETE {result.rowcount} codeable_concept_codings rows")

    # remove domain codings
    query = text("DELETE FROM codings WHERE system = :search_pattern")
    result = conn.execute(query, {'search_pattern': 'http://us.truenth.org/observation'})
    logger.info(f"DELETE {result.rowcount} codings rows (domain codings)")

    # remove link id & score codings
    query = text("DELETE FROM codings WHERE system = :search_pattern")
    result = conn.execute(query, {'search_pattern': 'https://eproms.truenth.org/api/codings/assessment'})
    logger.info(f"DELETE {result.rowcount} codings rows (link id & score)")

    # Remove the research protocols for research study ID 1 (EMPRO) and all the
    # related organization_research_protocol rows.
    query = text(
        "DELETE FROM organization_research_protocols WHERE research_protocol_id IN "
        "  (SELECT id FROM research_protocols WHERE research_study_id IN "
        "  (SELECT id FROM research_studies WHERE title = :search_pattern))"
    )
    result = conn.execute(query, {'search_pattern': 'IRONMAN EMPRO Study'})
    logger.info(f"DELETE {result.rowcount} organization_research_protocols rows")

    query = text(
        "DELETE FROM research_protocols WHERE research_study_id IN "
        "  (SELECT id FROM research_studies WHERE title = :search_pattern)"
    )
    result = conn.execute(query, {'search_pattern': 'IRONMAN EMPRO Study'})
    logger.info(f"DELETE {result.rowcount} research_protocols rows")

    query = text("DELETE FROM research_studies WHERE title = :search_pattern")
    result = conn.execute(query, {'search_pattern': 'IRONMAN EMPRO Study'})
    logger.info(f"DELETE {result.rowcount} research_studies rows")


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
