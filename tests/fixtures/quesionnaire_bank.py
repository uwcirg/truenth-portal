from flask_webtest import SessionScope
from pytest import fixture

from portal.database import db
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
    QuestionnaireBankQuestionnaire
)
from portal.models.recur import Recur


@fixture
def initialized_with_ss_qb(
        initialized_with_ss_protocol, initialized_with_ss_q):
    rp_id = db.session.merge(initialized_with_ss_protocol).id
    ss_qb = QuestionnaireBank(
        name='substudy_qb_baseline',
        start='{"days": 0}',
        expired='{"months": 1}',
        research_protocol_id=rp_id)
    qbq = QuestionnaireBankQuestionnaire(
        questionnaire=initialized_with_ss_q, rank=0)
    ss_qb.questionnaires.append(qbq)

    with SessionScope(db):
        db.session.add(ss_qb)
        db.session.commit()
    return db.session.merge(ss_qb)


@fixture
def initialized_with_ss_recur_qb(
        initialized_with_ss_protocol, initialized_with_ss_q):
    rp_id = db.session.merge(initialized_with_ss_protocol).id
    monthly_recur = Recur(
        start='{"months": 1}', cycle_length='{"months": 1}',
        termination='{"months": 11}')
    ss_qb = QuestionnaireBank(
        name='substudy_qb_monthly',
        start='{"days": 0}',
        expired='{"months": 1, "days": -1}',
        recurs=[monthly_recur],
        research_protocol_id=rp_id)
    qbq = QuestionnaireBankQuestionnaire(
        questionnaire=initialized_with_ss_q, rank=0)
    ss_qb.questionnaires.append(qbq)

    with SessionScope(db):
        db.session.add(ss_qb)
        db.session.commit()
    return db.session.merge(ss_qb)
