"""Test module for trigger_states blueprint """
import pytest
from statemachine.exceptions import TransitionNotAllowed

from portal.trigger_states.empro_domains import DomainTriggers
from portal.trigger_states.empro_states import (
    evaluate_triggers,
    initiate_trigger,
    users_trigger_state,
)


def test_initial_state(test_user):
    """Confirm unknown user gets initial state"""
    state = users_trigger_state(test_user.id)
    assert state.state == 'unstarted'


def test_initial_state_view(client, initialized_patient_logged_in):
    """Confirm unknown user gets initial state"""
    user_id = initialized_patient_logged_in.id
    results = client.get(f'/api/user/{user_id}/triggers')
    assert results.status_code == 200
    assert results.json['state'] == 'unstarted'


def test_bogus_transition(initialized_with_ss_qnr):
    """Attempt to jump to due without starting; expect exception"""
    with pytest.raises(TransitionNotAllowed):
        evaluate_triggers(initialized_with_ss_qnr)


def test_initiate_trigger(test_user):
    results = initiate_trigger(test_user.id)
    assert results.state == 'due'
    before = results.id

    # confirm idempotent second call
    results = initiate_trigger(test_user.id)
    assert results.state == 'due'
    assert before == results.id


def test_base_eval(
        test_user, initialized_with_ss_recur_qb, initialized_with_ss_qnr):
    from portal.database import db

    test_user_id = db.session.merge(test_user).id
    initiate_trigger(test_user_id)

    evaluate_triggers(initialized_with_ss_qnr)
    results = users_trigger_state(test_user_id)

    assert len(results.triggers['domain']) == 8


def test_cur_hard_trigger():
    # Single result with a severe should generate a hard (and soft) trigger
    dt = DomainTriggers('anxious')
    dt.current_answers = {15: 4, 12: 3, 21: 1}
    assert 'hard' in dt.triggers
    # hard trigger should implicitly add soft as well
    assert 'soft' in dt.triggers


def test_worsening_soft_trigger():
    # One point worsening from any q in domain should generate 'soft'
    dt = DomainTriggers('anxious')
    dt.previous_answers = {21: 2, 15: 2}
    dt.current_answers = {15: 3, 12: 3, 21: 1}
    assert 'soft' in dt.triggers
    assert 'hard' not in dt.triggers


def test_worsening_baseline():
    # Using mock'd results, confirm a hard trigger fires
    dt = DomainTriggers('anxious')
    dt.initial_answers = {21: 2, 15: 3}
    dt.previous_answers = {12: 3, 15: 3}
    dt.current_answers = {15: 3, 12: 3, 21: 3}
    assert 'soft' in dt.triggers
    assert 'hard' not in dt.triggers
