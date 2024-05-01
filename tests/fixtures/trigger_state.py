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
                '_sequential_hard_trigger_count': 3,
                '_opt_out_this_visit': True},
            'fatigue': {'ironman_ss.9': 'hard'},
            'anxious': {'ironman_ss.12': 'soft'},
        }
    }


@fixture
def mock_opted_out_triggers():
    # pulled from test db, user 4231, id 1063 as of 4/30/24
    return  {
        "domain": {
            "sad": {
                "ironman_ss.17": "hard",
                "ironman_ss.18": "hard",
                "ironman_ss.19": "hard",
                "_total_opted_out": 1,
                "_opt_out_this_visit": True,
                "_sequential_hard_trigger_count": 3},
            "anxious": {
                "ironman_ss.11": "hard",
                "ironman_ss.12": "hard",
                "ironman_ss.13": "hard",
                "_sequential_hard_trigger_count": 3},
            "fatigue": {
                "ironman_ss.9": "hard",
                "ironman_ss.10": "hard",
                "_sequential_hard_trigger_count": 3},
            "insomnia": {
                "ironman_ss.7": "hard",
                "ironman_ss.8": "hard",
                "_sequential_hard_trigger_count": 1},
            "joint_pain": {
                "ironman_ss.4": "hard",
                "ironman_ss.5": "hard",
                "ironman_ss.6": "hard",
                "_sequential_hard_trigger_count": 3},
            "discouraged": {
                "ironman_ss.14": "hard",
                "ironman_ss.15": "hard",
                "ironman_ss.16": "hard",
                "_sequential_hard_trigger_count": 3},
            "general_pain": {
                "ironman_ss.1": "soft",
                "ironman_ss.2": "soft",
                "ironman_ss.3": "soft",
                "_sequential_hard_trigger_count": 0},
            "social_isolation": {
                "ironman_ss.20": "hard",
                "_total_opted_out": 1,
                "_opt_out_this_visit": True,
                "_sequential_hard_trigger_count": 3}
        },
        "source": {
            "qb_id": 115,
            "qnr_id": 4841,
            "authored": "2024-04-25T19:24:57Z",
            "qb_iteration": 1},
        "actions": {
            "email": [
                {"context": "patient thank you", "timestamp": "2024-04-25T19:25:32.151704Z", "email_message_id": 214811},
                {"context": "initial staff alert", "timestamp": "2024-04-25T19:25:32.481573Z", "email_message_id": 214812},
                {"context": "initial staff alert", "timestamp": "2024-04-25T19:25:32.739550Z", "email_message_id": 214813},
                {"context": "initial staff alert", "timestamp": "2024-04-25T19:25:32.939555Z", "email_message_id": 214814},
                {"context": "initial staff alert", "timestamp": "2024-04-25T19:25:33.155603Z", "email_message_id": 214815},
                {"context": "initial staff alert", "timestamp": "2024-04-25T19:25:33.391523Z", "email_message_id": 214816},
                {"context": "initial staff alert", "timestamp": "2024-04-25T19:25:33.628547Z", "email_message_id": 214817},
                {"context": "initial staff alert", "timestamp": "2024-04-25T19:25:33.846962Z", "email_message_id": 214818},
                {"context": "initial staff alert", "timestamp": "2024-04-25T19:25:34.069484Z", "email_message_id": 214819}]
        },
        "resolution": {
            "qnr_id": 4842,
            "authored": "2024-04-25T19:26:51Z",
            "qb_iteration": None},
        "action_state": "completed"
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
