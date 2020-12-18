from flask_webtest import SessionScope
from pytest import fixture

from portal.database import db
from portal.models.identifier import Identifier
from portal.models.questionnaire import Questionnaire
from portal.system_uri import TRUENTH_QUESTIONNAIRE_CODE_SYSTEM


def persist_named_questionnaire(name):
    q = Questionnaire()
    i = Identifier(
        system=TRUENTH_QUESTIONNAIRE_CODE_SYSTEM,
        value=name)
    q.identifiers.append(i)
    with SessionScope(db):
        db.session.add(q)
        db.session.commit()
    return db.session.merge(q)


@fixture
def initialized_with_ss_q(initialized_db):
    return persist_named_questionnaire('substudy')
