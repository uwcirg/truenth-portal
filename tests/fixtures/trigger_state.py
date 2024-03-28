from pytest import fixture
from flask_webtest import SessionScope

from portal.database import db
from portal.trigger_states.models import TriggerState


@fixture
def mock_triggers():
    return {
        'domain': {
            'general_pain': {
                'ironman_ss.1': 'soft', 'ironman_ss.2': 'hard'},
            'joint_pain': {
                'ironman_ss.4': 'hard', 'ironman_ss.6': 'soft'},
            'insomnia': {
                '_sequential_hard_trigger_count': 2,
                '_opt_out_this_visit': True},
            'fatigue': {'ironman_ss.9': 'hard'},
            'anxious': {'ironman_ss.12': 'soft'},
        }
    }


@fixture
def processed_ts(initialized_patient, mock_triggers):
    user_id = db.session.merge(initialized_patient).id
    ts = TriggerState(
        state='processed',
        triggers=mock_triggers,
        user_id=user_id)
    with SessionScope(db):
        db.session.add(ts)
        db.session.commit()
    return db.session.merge(ts)


@fixture
def triggered_ts(initialized_patient, mock_triggers):
    user_id = db.session.merge(initialized_patient).id

    # add actions as if this ts has already been processed
    mock_alert = {
        'email_message_id': 111,
        'context': 'patient thank you',
        'timestamp': '2020-11-10T19:38:04.064253Z'}
    mock_triggers['actions'] = {'email': [mock_alert]}

    ts = TriggerState(
        state='triggered',
        triggers=mock_triggers,
        user_id=user_id)
    with SessionScope(db):
        db.session.add(ts)
        db.session.commit()
    return db.session.merge(ts)


@fixture
def opt_out_submission():
    return {
        "user_id": 1,
        "visit_month": 0,
        "triggers": {
            "domains": {
                "general_pain": {
                    "_opt_out_this_visit": True
                },
                "fatigue": {
                    "_opt_out_this_visit": True
                }
            }
        }
    }
