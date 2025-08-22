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


@fixture
def clinician_response_holiday_delay():
    data = {
        "group": {
            "question": [
                {
                    "text": "Action(s) Taken",
                    "answer": [
                        {"valueString": "Called and spoke with patient"},
                        {"valueCoding": {
                            "code": "ironman_ss_post_tx.1.1",
                            "system": "https://eproms.truenth.org/api/codings/assessment"}
                        },
                        {"valueCoding": {
                            "code": "ironman_ss_post_tx.1.5",
                            "system": "https://eproms.truenth.org/api/codings/assessment"},
                            "valueString": "Other (please specify)"
                        },
                        {"valueString": "just a test..."}
                    ],
                    "linkId": "ironman_ss_post_tx.1"
                },
                {
                    "text": "Date action taken",
                    "answer": [
                        {"valueString": "2022-06-17"}
                    ],
                    "linkId": "ironman_ss_post_tx.2"
                },
                {
                    "text": "Delayed due to local public holiday",
                    "answer": [{"valueBoolean": True}],
                    "linkId": "ironman_ss_post_tx.2.1"
                },
                {
                    "text": "Action taken by",
                    "answer": [
                        {"valueString": "Other"},
                        {"valueCoding": {
                            "code": "ironman_ss_post_tx.3.4",
                            "system": "https://eproms.truenth.org/api/codings/assessment"}
                        }
                    ],
                    "linkId": "ironman_ss_post_tx.3"
                },
                {
                    "text": "I confirm I have received this notification and taken action.",
                    "answer": [{"valueBoolean": True}],
                    "linkId": "ironman_ss_post_tx.4"
                }
            ]
        },
        "author": {
            "display": "user info",
            "reference": "https://eproms.truenth.org/api/me/4"
        },
        "source": {
            "display": "user demographics",
            "reference": "https://eproms.truenth.org/api/demographics/4"},
        "status": "completed",
        "subject": {
            "display": "patient demographics",
            "reference": "https://eproms.truenth.org/api/demographics/5051"
        },
        "authored": "2022-06-22T01:00:54Z",
        "resourceType": "QuestionnaireResponse",
        "questionnaire": {
            "display": "EMPRO Post Intervention Questionnaire",
            "reference": "https://eproms.truenth.org/api/questionnaires/ironman_ss_post_tx"}
    }

    return QuestionnaireResponse(document=data)
