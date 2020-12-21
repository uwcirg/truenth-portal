"""Rebuild qb_timeline for patients missing 6 month qb series

Revision ID: f93d9608c372
Revises: 894bbf6a8aa5
Create Date: 2020-04-10 07:16:41.276096

"""
from alembic import op
from collections import OrderedDict
from sqlalchemy.orm import sessionmaker

from portal.models.qb_timeline import QBT, update_users_QBT
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.questionnaire_response import QuestionnaireResponse
from portal.models.user import User

Session = sessionmaker()

# revision identifiers, used by Alembic.
revision = 'f93d9608c372'
down_revision = '894bbf6a8aa5'

def visit_name(qb_id, iteration):
    """special purpose for this migration"""
    if iteration == 0:
        return "6 month"
    elif iteration == 1:
        return "18 month"
    elif iteration == 2:
        return "30 month"
    raise RuntimeError("not possible")


def existing_qnr_deets(session, patient_id, missing_qb_id):
    """Display info WRT QuestionnaireResponses from the missing QBs"""
    qnrs = session.query(QuestionnaireResponse).filter(
        QuestionnaireResponse.subject_id == patient_id).filter(
        QuestionnaireResponse.questionnaire_bank_id == missing_qb_id).order_by(
        QuestionnaireResponse.authored.desc())

    results = OrderedDict()
    for q in qnrs:
        vn = visit_name(missing_qb_id, q.qb_iteration)
        if vn not in results:
            results[vn] = q.authored
    return results


def upgrade():
    session = Session(bind=op.get_bind())
    six_mo_qb = QuestionnaireBank.query.filter(
        QuestionnaireBank.name == 'IRONMAN_v3_recurring_6mo_pattern').first()
    if not six_mo_qb:
        # System w/o problem QB - nothing needed
        return
    six_mo_qb = six_mo_qb.id
    three_mo_qb = QuestionnaireBank.query.filter(
        QuestionnaireBank.name == 'IRONMAN_v3_recurring_3mo_pattern').first().id

    candidate_patients = [p[0] for p in session.query(QBT).filter(
        QBT.qb_id == three_mo_qb).distinct(
        QBT.user_id).with_entities(QBT.user_id)]
    already_golden = [p[0] for p in session.query(QBT).filter(
        QBT.qb_id == six_mo_qb).distinct(
        QBT.user_id).with_entities(QBT.user_id)]
    print("Found %d candidates, of which %d already have 6 mo QBs" % (
        len(candidate_patients), len(already_golden)))

    sys_user = User.query.filter_by(email='__system__').with_entities(User.id).one()[0]

    target_patients = set(candidate_patients) - set(already_golden)
    results = {}
    for tp in target_patients:
        # generate dots so it doesn't look hung, as this takes forever
        print('.', end='')

        for visit, authored in existing_qnr_deets(
                session, tp, six_mo_qb).items():
            results[authored] = (tp, visit)
        # Force reprocessing of QNR -> QB relationships and QB Timeline
        # to pick up missing QB and refresh any missing relationships
        QuestionnaireResponse.purge_qb_relationship(
            subject_id=tp, acting_user_id=sys_user)
        update_users_QBT(tp, invalidate_existing=True)

    date_sorted = {
        k: v for k, v in sorted(results.items(), key=lambda item: item[0])}
    for authored, tup in date_sorted.items():
        print("Patient %d posted results for %s on %s" % (
            tup[0], tup[1], authored))


def downgrade():
    # no going back
    pass
