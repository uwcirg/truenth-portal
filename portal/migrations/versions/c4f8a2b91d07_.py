"""fix physactivity valueCoding

Revision ID: c4f8a2b91d07
Revises: 8eb3e2e6076a
Create Date: 2026-07-12 21:40:00.000000

"""
from alembic import op
from copy import deepcopy
import json
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4f8a2b91d07'
down_revision = '8eb3e2e6076a'

CODING_SYSTEM = "https://eproms.truenth.org/api/codings/assessment"

PHYSACTIVITY_OPTION_MAP = {
    "physactivity.1.1": "Unable to walk",
    "physactivity.1.2": "Easy, casual (less than 2 mph)",
    "physactivity.1.3": "Normal, average (2-2.9 mph)",
    "physactivity.1.4": "Brisk pace (3-3.9 mph)",
    "physactivity.1.5": "Very brisk/striding (4 mph or faster)",
    "physactivity.2.1": "Zero",
    "physactivity.2.2": "1-4 minutes",
    "physactivity.2.3": "5-19 minutes",
    "physactivity.2.4": "20-59 minutes",
    "physactivity.2.5": "One hour",
    "physactivity.2.6": "1-1.5 hours",
    "physactivity.2.7": "2-3 hours",
    "physactivity.2.8": "4-6 hours",
    "physactivity.2.9": "7-10 hours",
    "physactivity.2.10": "11 or more hours",
    "physactivity.3.1": "Zero",
    "physactivity.3.2": "1-4 minutes",
    "physactivity.3.3": "5-19 minutes",
    "physactivity.3.4": "20-59 minutes",
    "physactivity.3.5": "One hour",
    "physactivity.3.6": "1-1.5 hours",
    "physactivity.3.7": "2-3 hours",
    "physactivity.3.8": "4-6 hours",
    "physactivity.3.9": "7-10 hours",
    "physactivity.3.10": "11 or more hours",
    "physactivity.4.1": "Zero",
    "physactivity.4.2": "1-4 minutes",
    "physactivity.4.3": "5-19 minutes",
    "physactivity.4.4": "20-59 minutes",
    "physactivity.4.5": "One hour",
    "physactivity.4.6": "1-1.5 hours",
    "physactivity.4.7": "2-3 hours",
    "physactivity.4.8": "4-6 hours",
    "physactivity.4.9": "7-10 hours",
    "physactivity.4.10": "11 or more hours",
    "physactivity.5.1": "Zero",
    "physactivity.5.2": "1-4 minutes",
    "physactivity.5.3": "5-19 minutes",
    "physactivity.5.4": "20-59 minutes",
    "physactivity.5.5": "One hour",
    "physactivity.5.6": "1-1.5 hours",
    "physactivity.5.7": "2-3 hours",
    "physactivity.5.8": "4-6 hours",
    "physactivity.5.9": "7-10 hours",
    "physactivity.5.10": "11 or more hours",
    "physactivity.6.1": "Low",
    "physactivity.6.2": "Medium",
    "physactivity.6.3": "High",
    "physactivity.7.1": "Zero",
    "physactivity.7.2": "1-4 minutes",
    "physactivity.7.3": "5-19 minutes",
    "physactivity.7.4": "20-59 minutes",
    "physactivity.7.5": "One hour",
    "physactivity.7.6": "1-1.5 hours",
    "physactivity.7.7": "2-3 hours",
    "physactivity.7.8": "4-6 hours",
    "physactivity.7.9": "7-10 hours",
    "physactivity.7.10": "11 or more hours",
    "physactivity.8.1": "Low",
    "physactivity.8.2": "Medium",
    "physactivity.8.3": "High",
    "physactivity.9.1": "Zero",
    "physactivity.9.2": "1-4 minutes",
    "physactivity.9.3": "5-19 minutes",
    "physactivity.9.4": "20-59 minutes",
    "physactivity.9.5": "One hour",
    "physactivity.9.6": "1-1.5 hours",
    "physactivity.9.7": "2-3 hours",
    "physactivity.9.8": "4-6 hours",
    "physactivity.9.9": "7-10 hours",
    "physactivity.9.10": "11 or more hours",
    "physactivity.10.1": "Low",
    "physactivity.10.2": "Medium",
    "physactivity.10.3": "High",
    "physactivity.11.1": "Zero",
    "physactivity.11.2": "1-4 minutes",
    "physactivity.11.3": "5-19 minutes",
    "physactivity.11.4": "20-59 minutes",
    "physactivity.11.5": "One hour",
    "physactivity.11.6": "1-1.5 hours",
    "physactivity.11.7": "2-3 hours",
    "physactivity.11.8": "4-6 hours",
    "physactivity.11.9": "7-10 hours",
    "physactivity.11.10": "11 or more hours",
    "physactivity.12.1": "Low",
    "physactivity.12.2": "Medium",
    "physactivity.12.3": "High",
    "physactivity.13.1": "Zero",
    "physactivity.13.2": "1-4 minutes",
    "physactivity.13.3": "5-19 minutes",
    "physactivity.13.4": "20-59 minutes",
    "physactivity.13.5": "One hour",
    "physactivity.13.6": "1-1.5 hours",
    "physactivity.13.7": "2-3 hours",
    "physactivity.13.8": "4-6 hours",
    "physactivity.13.9": "7-10 hours",
    "physactivity.13.10": "11 or more hours",
    "physactivity.14.1": "Low",
    "physactivity.14.2": "Medium",
    "physactivity.14.3": "High",
    "physactivity.15.1": "Zero",
    "physactivity.15.2": "1-4 minutes",
    "physactivity.15.3": "5-19 minutes",
    "physactivity.15.4": "20-59 minutes",
    "physactivity.15.5": "One hour",
    "physactivity.15.6": "1-1.5 hours",
    "physactivity.15.7": "2-3 hours",
    "physactivity.15.8": "4-6 hours",
    "physactivity.15.9": "7-10 hours",
    "physactivity.15.10": "11 or more hours",
    "physactivity.16.1": "Zero",
    "physactivity.16.2": "1-4 minutes",
    "physactivity.16.3": "5-19 minutes",
    "physactivity.16.4": "20-59 minutes",
    "physactivity.16.5": "One hour",
    "physactivity.16.6": "1-1.5 hours",
    "physactivity.16.7": "2-3 hours",
    "physactivity.16.8": "4-6 hours",
    "physactivity.16.9": "7-10 hours",
    "physactivity.16.10": "11 or more hours",
    "physactivity.17.1": "Zero",
    "physactivity.17.2": "1-4 minutes",
    "physactivity.17.3": "5-19 minutes",
    "physactivity.17.4": "20-59 minutes",
    "physactivity.17.5": "One hour",
    "physactivity.17.6": "1-1.5 hours",
    "physactivity.17.7": "2-3 hours",
    "physactivity.17.8": "4-6 hours",
    "physactivity.17.9": "7-10 hours",
    "physactivity.17.10": "11 or more hours",
    "physactivity.18.1": "Zero",
    "physactivity.18.2": "1-4 minutes",
    "physactivity.18.3": "5-19 minutes",
    "physactivity.18.4": "20-59 minutes",
    "physactivity.18.5": "One hour",
    "physactivity.18.6": "1-1.5 hours",
    "physactivity.18.7": "2-3 hours",
    "physactivity.18.8": "4-6 hours",
    "physactivity.18.9": "7-10 hours",
    "physactivity.18.10": "11 or more hours",
    "physactivity.19.1": "Zero",
    "physactivity.19.2": "1-4 minutes",
    "physactivity.19.3": "5-19 minutes",
    "physactivity.19.4": "20-59 minutes",
    "physactivity.19.5": "One hour",
    "physactivity.19.6": "1-1.5 hours",
    "physactivity.19.7": "2-3 hours",
    "physactivity.19.8": "4-6 hours",
    "physactivity.19.9": "7-10 hours",
    "physactivity.19.10": "11 or more hours",
    "physactivity.20.1": "Zero hours",
    "physactivity.20.2": "One hour",
    "physactivity.20.3": "2-5 hours",
    "physactivity.20.4": "6-10 hours",
    "physactivity.20.5": "11-20 hours",
    "physactivity.20.6": "21-40 hours",
    "physactivity.20.7": "41-60 hours",
    "physactivity.20.8": "61-90 hours",
    "physactivity.20.9": "Over 90 hours",
    "physactivity.21.1": "Zero hours",
    "physactivity.21.2": "One hour",
    "physactivity.21.3": "2-5 hours",
    "physactivity.21.4": "6-10 hours",
    "physactivity.21.5": "11-20 hours",
    "physactivity.21.6": "21-40 hours",
    "physactivity.21.7": "41-60 hours",
    "physactivity.21.8": "61-90 hours",
    "physactivity.21.9": "Over 90 hours",
    "physactivity.22.1": "Zero hours",
    "physactivity.22.2": "One hour",
    "physactivity.22.3": "2-5 hours",
    "physactivity.22.4": "6-10 hours",
    "physactivity.22.5": "11-20 hours",
    "physactivity.22.6": "21-40 hours",
    "physactivity.22.7": "41-60 hours",
    "physactivity.22.8": "61-90 hours",
    "physactivity.22.9": "Over 90 hours",
    "physactivity.23.1": "Zero hours",
    "physactivity.23.2": "One hour",
    "physactivity.23.3": "2-5 hours",
    "physactivity.23.4": "6-10 hours",
    "physactivity.23.5": "11-20 hours",
    "physactivity.23.6": "21-40 hours",
    "physactivity.23.7": "41-60 hours",
    "physactivity.23.8": "61-90 hours",
    "physactivity.23.9": "Over 90 hours",
    "physactivity.24.1": "Zero hours",
    "physactivity.24.2": "One hour",
    "physactivity.24.3": "2-5 hours",
    "physactivity.24.4": "6-10 hours",
    "physactivity.24.5": "11-20 hours",
    "physactivity.24.6": "21-40 hours",
    "physactivity.24.7": "41-60 hours",
    "physactivity.24.8": "61-90 hours",
    "physactivity.24.9": "Over 90 hours",
}


def _build_physactivity_lookup():
    lookup = {}
    for code, text in PHYSACTIVITY_OPTION_MAP.items():
        link_id = code.rsplit(".", 1)[0]
        lookup[(link_id, text)] = code
    return lookup


PHYSACTIVITY_LOOKUP = _build_physactivity_lookup()


def lookup_code(link_id, value_string):
    return PHYSACTIVITY_LOOKUP.get((link_id, value_string))


def update_physactivity_codes(document: dict) -> dict:
    """Add missing valueCoding entries for physactivity answers."""
    doc = deepcopy(document)
    for question in doc.get("group", {}).get("question", []):
        link_id = question.get("linkId", "")
        if not link_id.startswith("physactivity"):
            continue
        answers = question.get("answer", [])
        existing_codes = {
            a["valueCoding"]["code"]
            for a in answers
            if a.get("valueCoding", {}).get("code")
        }
        for answer in list(answers):
            value_string = answer.get("valueString")
            if not value_string:
                continue
            code = lookup_code(link_id, value_string)
            if not code or code in existing_codes:
                continue
            answers.append({
                "valueCoding": {
                    "code": code,
                    "system": CODING_SYSTEM,
                    "text": value_string,
                }
            })
            existing_codes.add(code)
    return doc


def upgrade():
    conn = op.get_bind()

    result = conn.execute(sa.text("""
        SELECT id, document
        FROM questionnaire_responses
        WHERE document->'questionnaire'->>'reference' ILIKE '%physactivity'
    """))
    rows = result.fetchall()

    for row in rows:
        doc_id = row["id"]
        document = row["document"]

        if not document:
            continue

        updated_document = update_physactivity_codes(document)

        if updated_document != document:
            conn.execute(
                sa.text(
                    "UPDATE questionnaire_responses SET document = :document WHERE id = :id"
                ),
                {"document": json.dumps(updated_document), "id": doc_id},
            )
            print("Updated QNR: ", doc_id)


def downgrade():
    pass
