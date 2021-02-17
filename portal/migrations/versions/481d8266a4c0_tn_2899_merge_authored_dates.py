"""TN-2899 merge authored dates so all QNRs have single authored value.

Revision ID: 481d8266a4c0
Revises: c19bff0f70ab
Create Date: 2021-01-19 12:56:24.651157

"""
from alembic import op
import copy
from datetime import datetime
from flask import current_app
import json
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '481d8266a4c0'
down_revision = 'c19bff0f70ab'


def upgrade():
    """As per TN-2899 forensics, if the QNR was a "paper entry", use
    the older of `authored` or `document.authored`

    Otherwise update `authored` to the value of `document.authored`
    when found to differ.

    All updates require audit entries.
    """
    conn = op.get_bind()
    admin_id = conn.execute(
        "SELECT id FROM users WHERE email = '__system__'"
    ).next()[0]
    paper_code = conn.execute(
        "SELECT id FROM codings WHERE"
        " system = 'http://us.truenth.org/encounter-types' AND"
        " code = 'paper'").next()[0]
    those_with_diffs = (
        "SELECT questionnaire_responses.id as id, subject_id, authored,"
        " TO_TIMESTAMP(document->>'authored', 'YYYY-MM-DDTHH24:MI:SS')::timestamp without time zone AS doc_authored,"
        " coding_id, document FROM questionnaire_responses"
        " LEFT JOIN encounter_codings"
        " ON questionnaire_responses.encounter_id = encounter_codings.encounter_id"
        " WHERE authored != TO_TIMESTAMP(document->>'authored', 'YYYY-MM-DDTHH24:MI:SS')::timestamp without time zone;"
    )
    result = conn.execute(those_with_diffs)
    preferred_authored = []
    preferred_doc_auth = []
    for row in result:
        if row['coding_id'] == paper_code:
            # Keep the older
            if row['authored'] < row['doc_authored']:
                # Exceptional case: prefer top `authored`
                preferred_authored.append({
                    'qnr_id': row['id'],
                    'subject_id': row['subject_id'],
                    'authored': row['authored'],
                    'doc_authored': row['doc_authored'],
                    'document': row['document']})
                continue

        # Common case, keep doc authored
        preferred_doc_auth.append({
            'qnr_id': row['id'],
            'subject_id': row['subject_id'],
            'authored': row['authored'],
            'doc_authored': row['doc_authored']})

    # nature of joins and some QNRs being both "paper" and
    # "interview_assisted", prefer the paper exceptions and
    # don't set back on the interview assisted occurrence
    paper_exception_ids = [i['qnr_id'] for i in preferred_authored]

    now = datetime.utcnow()
    version = current_app.config.metadata['version']

    def audit_insert(subject_id, msg):
        insert = (
            "INSERT INTO AUDIT"
            " (user_id, subject_id, context, timestamp, version, comment)"
            " VALUES"
            f"({admin_id}, {i['subject_id']}, 'assessment',"
            f" '{now}', '{version}', '{msg}')")
        conn.execute(insert)

    print(f"found {len(preferred_authored)} for preferred authored")
    print(f"found {len(preferred_doc_auth)} for preferred document authored")

    for i in preferred_doc_auth:
        if i['qnr_id'] in paper_exception_ids:
            continue
        message = (
            f"Updated QNR {i['qnr_id']} authored from {i['authored']} to "
            f"{i['doc_authored']} as per TN-2899")
        audit_insert(i['subject_id'], message)

        mod_qnr = (
            f"UPDATE questionnaire_responses SET authored = '{i['doc_authored']}'"
            f" WHERE id = {i['qnr_id']}")
        conn.execute(mod_qnr)

    for i in preferred_authored:
        message = (
            f"Updated QNR {i['qnr_id']} authored from {i['doc_authored']} to "
            f"{i['authored']} as per TN-2899, given paper entry")
        audit_insert(i['subject_id'], message)

        new_doc = copy.deepcopy(i['document'])
        new_doc['authored'] = datetime.strftime(i['authored'], "%Y-%m-%dT%H:%M:%SZ")
        mod_qnr = (
            f"UPDATE questionnaire_responses SET document=:doc"
            f" WHERE id = {i['qnr_id']}")
        conn.execute(text(mod_qnr), doc=json.dumps(new_doc))


def downgrade():
    # No downgrade available for this migration.
    pass
