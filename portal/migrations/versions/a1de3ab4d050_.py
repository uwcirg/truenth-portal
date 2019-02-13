"""Remove duplicate QNR.identifiers

Revision ID: a1de3ab4d050
Revises: 55469bdd181f
Create Date: 2019-02-11 16:48:55.332527

"""
import json
from sqlalchemy import func
from portal.database import db
from portal.dict_tools import dict_compare
from portal.models.audit import Audit
from portal.models.identifier import Identifier
from portal.models.questionnaire_response import QuestionnaireResponse
from portal.models.user import User

# revision identifiers, used by Alembic.
revision = 'a1de3ab4d050'
down_revision = '55469bdd181f'


def admin_id():
    sys = User.query.filter_by(email='__system__').first()
    return sys.id


def diff_docs(doc1, doc2):
    """Print details of two differing QNR documents"""
    added, removed, modified, _ = dict_compare(doc1, doc2)
    assert not added
    assert not removed
    assert not set(modified) - set(['authored', 'group'])
    if modified:
        if len(doc1['group']) != len(doc2['group']):
            raise ValueError("diff group lens")
        answers1 = doc1['group']
        answers2 = doc2['group']
        for a1, a2 in zip(answers1, answers2):
            assert a1.keys() == a2.keys()
            assert (a1['answer']['valueCoding']['code'] ==
                    a2['answer']['valueCoding']['code'])
            if (a1['answer']['valueCoding']['extension']['valueDecimal'] !=
                    a2['answer']['valueCoding']['extension']['valueDecimal']):
                print("  Question: {} valueDecimal: {} VERSUS {}".format(
                    a1['answer']['valueCoding']['code'],
                    a1['answer']['valueCoding']['extension']['valueDecimal'],
                    a2['answer']['valueCoding']['extension']['valueDecimal']))


def merge_duplicates(system, value):
    msg = "merging questionnaire_responses with identifier ({}|{})".format(
        system, value)
    identifier = Identifier(system=system, value=value)
    qnrs = QuestionnaireResponse.by_identifier(identifier)

    print("found {} duplicates {}".format(len(qnrs), msg))

    subject_ids = {q.subject_id for q in qnrs}
    if len(subject_ids) != 1:
        raise ValueError("ERROR, expect single subject {}".format(msg))

    docs = [q.document for q in qnrs]
    json_docs = {json.dumps(q.document) for q in qnrs}
    if len(json_docs) != 1:
        print("SKIP {} due to mismatching documents".format(
            msg))
        d1 = docs.pop()
        while True:
            d2 = docs.pop()
            diff_docs(d1, d2)
            d1 = d2
            if not docs:
                break
        return  # skipping out due to document mismatch

    # Looks like perfect matches across the board - lets keep the first only
    del_ids = [q.id for q in qnrs][1:]
    audit = Audit(
        user_id=admin_id(), subject_id=subject_ids.pop(),
        _context='assessment',
        comment="{} eliminating duplicate qnr.ids ({})".format(
            msg, str(del_ids)))
    db.session.add(audit)

    QuestionnaireResponse.query.filter(
        QuestionnaireResponse.id.in_(del_ids)).delete(
        synchronize_session='fetch')
    db.session.commit()


def upgrade():
    # Only concerned about QuestionnaireResponses with more than
    # one matching identifier
    q = db.session.query(
        QuestionnaireResponse.document['identifier']['system'],
        QuestionnaireResponse.document['identifier']['value']).filter(
        QuestionnaireResponse.document['identifier'].isnot(None)).group_by(
        QuestionnaireResponse.document['identifier']['system'],
        QuestionnaireResponse.document['identifier']['value']).having(
        func.count(QuestionnaireResponse.document['identifier']) > 1)

    # gather list of (system, value) tuples for subsequent attention.
    # can't process inside query loop
    needs_attention = [(system, value) for system, value in q]

    for system, value in needs_attention:
        merge_duplicates(system, value)


def downgrade():
    # Don't restore that mess
    pass
