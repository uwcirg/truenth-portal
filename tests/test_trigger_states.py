"""Test module for trigger_states blueprint """
import pytest
from statemachine.exceptions import TransitionNotAllowed

from portal.database import db
from portal.models.role import ROLE
from portal.trigger_states.empro_domains import DomainTriggers
from portal.trigger_states.empro_states import (
    enter_user_trigger_critical_section,
    evaluate_triggers,
    fire_trigger_events,
    initiate_trigger,
    users_trigger_state,
)
from portal.trigger_states.models import TriggerState


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


def test_qnr_identifier(initialized_with_ss_qnr):
    from portal.models.reference import Reference
    ref = Reference.questionnaire_response(
        initialized_with_ss_qnr.document_identifier)
    assert ref.as_fhir()['reference'] == (
        'https://stg-ae.us.truenth.org/eproms-demo/QuestionnaireResponse/538.0'
    )


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
    test_user_id = db.session.merge(test_user).id
    initiate_trigger(test_user_id)

    evaluate_triggers(initialized_with_ss_qnr)
    results = users_trigger_state(test_user_id)

    assert 'domain' in results.triggers

    ts = TriggerState.query.filter(
        TriggerState.user_id == test_user_id).filter(
        TriggerState.state == 'processed').one()
    assert ts.questionnaire_response_id == initialized_with_ss_qnr.id


def test_cur_hard_trigger():
    # Single result with a severe should generate a hard (and soft) trigger
    dt = DomainTriggers(
        domain='anxious',
        current_answers={
            'ironman_ss.12': (3, None),
            'ironman_ss.11': (2, None),
            'ironman_ss.13': (4, 'penultimate')},
        previous_answers=None,
        initial_answers=None)
    assert len(dt.triggers) == 1
    assert 'ironman_ss.13' in dt.triggers


def test_worsening_soft_trigger():
    # One point worsening from any q in domain should generate 'soft'
    dt = DomainTriggers(
        domain='anxious',
        previous_answers={'ss.21': (2, None), 'ss.15': (2, None)},
        current_answers={
            'ss.15': (3, None), 'ss.12': (3, None), 'ss.21': (1, None)},
        initial_answers=None)
    assert len(dt.triggers) == 1
    assert dt.triggers['ss.15'] == 'soft'


def test_worsening_baseline():
    # confirm a hard trigger with 2 level worsening
    initial_answers = {15: (3, None), 21: (1, None)}
    previous_answers = {12: (1, None), 15: (3, None)}
    current_answers = {12: (3, None), 15: (3, None), 21: (3, None)}
    dt = DomainTriggers(
        domain='anxious',
        initial_answers=initial_answers,
        previous_answers=previous_answers,
        current_answers=current_answers)

    assert len(dt.triggers) == 2
    assert dt.triggers[12] == dt.triggers[21] == 'hard'


def test_ts_trigger_lists(mock_triggers):
    ts = TriggerState(state='processed', triggers=mock_triggers, user_id=1)
    assert set(['general_pain', 'joint_pain', 'fatigue']) == set(
        ts.hard_trigger_list())
    assert set(['general_pain', 'joint_pain', 'anxious', 'fatigue']) == set(
        ts.soft_trigger_list())


def test_fire_trigger_events(initialized_patient, processed_ts, promote_user):
    # pretend patient is it's own clinician for staff email
    user = db.session.merge(initialized_patient)
    user_id = user.id
    user.clinician_id = user.id
    promote_user(user=user, role_name=ROLE.CLINICIAN.value)

    fire_trigger_events()

    # user's trigger should now include actions and with hard
    # triggers, should still be triggered with an action for staff
    # and patient
    ts = users_trigger_state(user_id)
    assert ts.state == 'triggered'
    assert len(ts.triggers['actions']['email']) > 1


def test_fire_reminders(initialized_patient, triggered_ts, promote_user):
    # pretend patient is it's own clinician for staff email
    user = db.session.merge(initialized_patient)
    user_id = user.id
    user.clinician_id = user.id
    promote_user(user=user, role_name=ROLE.CLINICIAN.value)

    fire_trigger_events()

    # user's trigger should now include actions and with hard
    # triggers, should still be triggered with an action for staff
    # and patient
    ts = users_trigger_state(user_id)
    assert ts.state == 'triggered'
    assert len(ts.triggers['actions']['email']) > 1
    assert 'reminder' in ts.triggers['actions']['email'][-1]['context']
