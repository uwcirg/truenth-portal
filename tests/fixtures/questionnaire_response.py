from flask_webtest import SessionScope
from pytest import fixture

from portal.database import db
from portal.models.encounter import Encounter
from portal.models.questionnaire_response import QuestionnaireResponse


@fixture
def initialized_with_ss_qnr(test_user, initialized_with_ss_qb):
    test_user_id = db.session.merge(test_user).id
    instrument_id = 'empro'
    doc_id = '538.0'
    timestamp = '2020-09-30T00:00:00Z'
    qr_document = {
        "authored": timestamp,
        "questionnaire": {
            "display": "Additional questions",
            "reference":
                "https://{}/api/questionnaires/{}".format(
                    'SERVER_NAME', instrument_id)},
        "identifier": {
            "use": "official",
            "label": "cPRO survey session ID",
            "value": doc_id,
            "system": "https://stg-ae.us.truenth.org/eproms-demo"}
    }
    encounter = Encounter(
        user_id=test_user_id,
        start_time=timestamp,
        status='in-progress',
        auth_method='password_authenticated')
    qnr = QuestionnaireResponse(
        document=qr_document,
        encounter=encounter,
        subject_id=test_user_id,
        status='completed',
        questionnaire_bank=initialized_with_ss_qb)
    with SessionScope(db):
        db.session.add(encounter)
        db.session.add(qnr)
        db.session.commit()
    return db.session.merge(qnr)
