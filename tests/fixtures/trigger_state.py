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
            'insomnia': {},
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
