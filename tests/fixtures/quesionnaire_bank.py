from flask_webtest import SessionScope
from pytest import fixture

from portal.database import db
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
)


@fixture
def initialized_with_substudy_qb(initialized_with_ss_protocol):
    ss_qb = QuestionnaireBank(
        name='substudy_qb',
        start='{"days": 0}',
        expired='{"months": 1}',
        research_protocol_id=initialized_with_ss_protocol.id)
    with SessionScope(db):
        db.session.add(ss_qb)
        db.session.commit()
    return db.session.merge(ss_qb)
