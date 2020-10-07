"""Unit test module for Intervention API"""

from datetime import datetime, timedelta
import json
import os

from dateutil.relativedelta import relativedelta
from flask_webtest import SessionScope
import pytest

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.clinical_constants import CC
from portal.models.group import Group
from portal.models.identifier import Identifier
from portal.models.intervention import (
    INTERVENTION,
    Intervention,
    UserIntervention,
)
from portal.models.intervention_strategies import AccessStrategy
from portal.models.message import EmailMessage
from portal.models.organization import Organization
from portal.models.qb_timeline import invalidate_users_QBT
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.research_study import ResearchStudy
from portal.models.role import ROLE
from portal.models.user import User, add_role
from portal.models.user_consent import UserConsent
from portal.system_uri import DECISION_SUPPORT_GROUP, SNOMED
from tests import TEST_USER_ID, associative_backdate
from tests.test_assessment_status import (
    metastatic_baseline_instruments,
    mock_qr,
    mock_questionnairebanks,
)


@pytest.fixture
def admin_user(test_user, promote_user):
    promote_user(role_name=ROLE.ADMIN.value)
    return test_user


@pytest.fixture
def patient_user(test_user, promote_user):
    promote_user(role_name=ROLE.PATIENT.value)
    return test_user


def test_intervention_wrong_service_user(
        service_user, login, client, deepen_org_tree):
    service_user = db.session.merge(service_user)
    login(user_id=service_user.id)

    data = {'user_id': TEST_USER_ID, 'access': 'granted'}
    response = client.put(
        '/api/intervention/sexual_recovery',
        content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 401


def test_intervention(
        test_client, service_user,
        login, client, deepen_org_tree):
    test_client = db.session.merge(test_client)
    test_client.intervention = INTERVENTION.SEXUAL_RECOVERY
    test_client.application_origins = 'http://safe.com'
    service_user = db.session.merge(service_user)
    login(user_id=service_user.id)

    data = {
        'user_id': TEST_USER_ID,
        'access': "granted",
        'card_html': "unique HTML set via API",
        'link_label': 'link magic',
        'link_url': 'http://safe.com',
        'status_text': 'status example',
        'staff_html': "unique HTML for /patients view"
    }

    response = client.put(
        '/api/intervention/sexual_recovery',
        content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 200

    ui = UserIntervention.query.one()
    assert ui.user_id == data['user_id']
    assert ui.access == data['access']
    assert ui.card_html == data['card_html']
    assert ui.link_label == data['link_label']
    assert ui.link_url == data['link_url']
    assert ui.status_text == data['status_text']
    assert ui.staff_html == data['staff_html']


def test_music_hack(
        test_client, service_user,
        login, client, deepen_org_tree):
    test_client = db.session.merge(test_client)
    test_client.intervention = INTERVENTION.MUSIC
    test_client.application_origins = 'http://safe.com'
    service_user = db.session.merge(service_user)
    login(user_id=service_user.id)

    data = {'user_id': TEST_USER_ID, 'access': "granted"}

    response = client.put(
        '/api/intervention/music',
        content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 200

    ui = UserIntervention.query.one()
    assert ui.user_id == data['user_id']
    assert ui.access == 'subscribed'


def test_intervention_partial_put(
        test_client, service_user,
        login, client, deepen_org_tree):
    test_client = db.session.merge(test_client)
    test_client.intervention = INTERVENTION.SEXUAL_RECOVERY
    test_client.application_origins = 'http://safe.com'
    service_user = db.session.merge(service_user)
    login(user_id=service_user.id)

    # Create a full UserIntervention row to attempt
    # a partial put on below
    data = {
        'user_id': TEST_USER_ID,
        'access': "granted",
        'card_html': "unique HTML set via API",
        'link_label': 'link magic',
        'link_url': 'http://safe.com',
        'status_text': 'status example',
        'staff_html': "unique HTML for /patients view"
    }

    ui = UserIntervention(
        user_id=data['user_id'], access=data['access'],
        card_html=data['card_html'], link_label=data['link_label'],
        link_url=data['link_url'], status_text=data['status_text'],
        staff_html=data['staff_html'],
        intervention_id=INTERVENTION.SEXUAL_RECOVERY.id)
    with SessionScope(db):
        db.session.add(ui)
        db.session.commit()

    # now just update a couple, but expect full data set (with
    # merged updates) to be returned
    update = {
        'user_id': TEST_USER_ID,
        'access': "forbidden",
        'card_html': "no access for YOU"
    }

    response = client.put(
        '/api/intervention/sexual_recovery',
        content_type='application/json',
        data=json.dumps(update))
    assert response.status_code == 200

    ui = UserIntervention.query.one()
    assert ui.user_id == data['user_id']
    assert ui.access == update['access']
    assert ui.card_html == update['card_html']
    assert ui.link_label == data['link_label']
    assert ui.link_url == data['link_url']
    assert ui.status_text == data['status_text']
    assert ui.staff_html == data['staff_html']


def test_intervention_bad_access(
        test_client, service_user,
        login, client, deepen_org_tree):
    test_client = db.session.merge(test_client)
    test_client.intervention = INTERVENTION.SEXUAL_RECOVERY
    service_user = db.session.merge(service_user)
    login(user_id=service_user.id)

    data = {
        'user_id': TEST_USER_ID,
        'access': 'enabled',
    }

    response = client.put(
        '/api/intervention/sexual_recovery',
        content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 400


def test_intervention_validation(
        test_client, service_user,
        login, client, deepen_org_tree):
    test_client = db.session.merge(test_client)
    test_client.intervention = INTERVENTION.SEXUAL_RECOVERY
    test_client.application_origins = 'http://safe.com'
    service_user = db.session.merge(service_user)
    login(user_id=service_user.id)

    data = {
        'user_id': TEST_USER_ID,
        'link_url': 'http://un-safe.com',
    }

    response = client.put(
        '/api/intervention/sexual_recovery',
        content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 400


def test_clinc_id(initialize_static, test_user):
    # Create several orgs with identifier
    org1 = Organization(name='org1')
    org2 = Organization(name='org2')
    org3 = Organization(name='org3')
    identifier = Identifier(value='pick me', system=DECISION_SUPPORT_GROUP)
    for org in (org1, org2, org3):
        org.identifiers.append(identifier)

    # Add access strategy to the care plan intervention
    cp = INTERVENTION.CARE_PLAN
    cp.public_access = False  # turn off public access to force strategy
    cp_id = cp.id

    with SessionScope(db):
        db.session.add(org1)
        db.session.add(org2)
        db.session.add(org3)
        db.session.commit()

    org1 = db.session.merge(org1)
    org2 = db.session.merge(org2)
    org3 = db.session.merge(org3)
    d = {
        'function': 'limit_by_clinic_w_id',
        'kwargs': [{'name': 'identifier_value',
                    'value': 'pick me'}]
    }
    strat = AccessStrategy(
        name="member of org with identifier",
        intervention_id=cp_id,
        function_details=json.dumps(d))

    with SessionScope(db):
        db.session.add(strat)
        db.session.commit()

    cp = INTERVENTION.CARE_PLAN
    user = db.session.merge(test_user)

    # Prior to associating user with any orgs, shouldn't have access
    assert not cp.display_for_user(user).access
    assert not cp.quick_access_check(user)

    # Add association and test again
    user.organizations.append(org3)
    with SessionScope(db):
        db.session.commit()
    user, cp = map(db.session.merge, (user, cp))
    assert cp.display_for_user(user).access
    assert cp.quick_access_check(user)


def test_diag_stategy(
        initialize_static, test_user,
        login, deepen_org_tree):
    """Test strategy for diagnosis"""
    # Add access strategies to the care plan intervention
    cp = INTERVENTION.CARE_PLAN
    cp.public_access = False  # turn off public access to force strategy
    cp_id = cp.id

    with SessionScope(db):
        d = {'function': 'observation_check',
             'kwargs': [
                 {
                     'name': 'display',
                     'value': CC.PCaDIAG.codings[0].display
                 },
                 {'name': 'boolean_value', 'value': 'true'}]}
        strat = AccessStrategy(
            name="has PCa diagnosis",
            intervention_id=cp_id,
            function_details=json.dumps(d))
        db.session.add(strat)
        db.session.commit()
    cp = INTERVENTION.CARE_PLAN
    user = db.session.merge(test_user)

    # Prior to PCa dx, user shouldn't have access
    assert not cp.display_for_user(user).access
    assert not cp.quick_access_check(user)

    # Bless the test user with PCa diagnosis
    login()
    user.save_observation(
        codeable_concept=CC.PCaDIAG, value_quantity=CC.TRUE_VALUE,
        audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
        status='registered', issued=None)
    with SessionScope(db):
        db.session.commit()
    user, cp = map(db.session.merge, (user, cp))

    assert cp.display_for_user(user).access
    assert cp.quick_access_check(user)


def test_diag_changed_stategy(test_user, login, deepen_org_tree):
    """Test strategy for altered diagnosis"""
    # Add access strategies to the care plan intervention
    cp = INTERVENTION.CARE_PLAN
    cp.public_access = False  # turn off public access to force strategy
    cp_id = cp.id

    with SessionScope(db):
        d = {'function': 'observation_check',
             'kwargs': [
                 {'name': 'display',
                  'value': CC.PCaDIAG.codings[0].display},
                 {'name': 'boolean_value', 'value': 'true'}]}
        strat = AccessStrategy(
            name="has PCa diagnosis",
            intervention_id=cp_id,
            function_details=json.dumps(d))
        db.session.add(strat)
        db.session.commit()
    cp = INTERVENTION.CARE_PLAN
    user = db.session.merge(test_user)

    # Prior to PCa dx, user shouldn't have access
    assert not cp.display_for_user(user).access
    assert not cp.quick_access_check(user)

    # Bless the test user with PCa diagnosis
    login()
    now = datetime.utcnow()
    before = now - relativedelta(hours=1)
    user.save_observation(
        codeable_concept=CC.PCaDIAG, value_quantity=CC.TRUE_VALUE,
        audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
        status='registered', issued=before)
    with SessionScope(db):
        db.session.commit()
    user, cp = map(db.session.merge, (user, cp))

    assert cp.display_for_user(user).access
    assert cp.quick_access_check(user)

    # Now post a *NEW* value taking away PCa dx, should eclipse old value
    # and tak away access
    user.save_observation(
        codeable_concept=CC.PCaDIAG, value_quantity=CC.FALSE_VALUE,
        audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
        status='registered', issued=now)
    with SessionScope(db):
        db.session.commit()
    user, cp = map(db.session.merge, (user, cp))

    assert not cp.display_for_user(user).access
    assert not cp.quick_access_check(user)


def test_no_tx(initialize_static, test_user, add_procedure):
    """Test strategy for not starting treatment"""
    # Add access strategies to the care plan intervention
    cp = INTERVENTION.CARE_PLAN
    cp.public_access = False  # turn off public access to force strategy
    cp_id = cp.id

    with SessionScope(db):
        d = {'function': 'tx_begun',
             'kwargs': [{'name': 'boolean_value', 'value': 'false'}]}
        strat = AccessStrategy(
            name="has not stared treatment",
            intervention_id=cp_id,
            function_details=json.dumps(d))
        db.session.add(strat)
        db.session.commit()
    cp = INTERVENTION.CARE_PLAN
    user = db.session.merge(test_user)

    # Prior to declaring TX, user should have access
    assert cp.display_for_user(user).access
    assert cp.quick_access_check(user)

    add_procedure(
        code='424313000', display='Started active surveillance')
    with SessionScope(db):
        db.session.commit()
    user, cp = map(db.session.merge, (user, cp))

    # Declaring they started a non TX proc, should still have access
    assert cp.display_for_user(user).access
    assert cp.quick_access_check(user)

    add_procedure(
        code='26294005',
        display='Radical prostatectomy (nerve-sparing)',
        system=SNOMED)
    with SessionScope(db):
        db.session.commit()
    user, cp = map(db.session.merge, (user, cp))

    # Declaring they started a TX proc, should lose access
    assert not cp.display_for_user(user).access
    assert not cp.quick_access_check(user)


def test_exclusive_stategy(initialize_static, test_user):
    """Test exclusive intervention strategy"""
    user = db.session.merge(test_user)
    ds_p3p = INTERVENTION.DECISION_SUPPORT_P3P
    ds_wc = INTERVENTION.DECISION_SUPPORT_WISERCARE

    ds_p3p.public_access = False
    ds_wc.public_access = False

    with SessionScope(db):
        d = {'function': 'allow_if_not_in_intervention',
             'kwargs': [{
                 'name': 'intervention_name', 'value': ds_wc.name}]}
        strat = AccessStrategy(
            name="exclusive decision support strategy",
            intervention_id=ds_p3p.id,
            function_details=json.dumps(d))
        db.session.add(strat)
        db.session.commit()
    user, ds_p3p, ds_wc = map(db.session.merge, (user, ds_p3p, ds_wc))

    # Prior to associating user w/ decision support, the strategy
    # should give access to p3p
    assert ds_p3p.display_for_user(user).access
    assert ds_p3p.quick_access_check(user)
    assert not ds_wc.display_for_user(user).access
    assert not ds_wc.quick_access_check(user)

    # Add user to wisercare, confirm it's the only w/ access

    ui = UserIntervention(user_id=user.id, intervention_id=ds_wc.id,
                          access='granted')
    with SessionScope(db):
        db.session.add(ui)
        db.session.commit()
    user, ds_p3p, ds_wc = map(db.session.merge, (user, ds_p3p, ds_wc))

    assert not ds_p3p.display_for_user(user).access
    assert not ds_p3p.quick_access_check(user)
    assert ds_wc.display_for_user(user).access
    assert ds_wc.quick_access_check(user)


def test_not_in_role_or_sr(initialize_static, test_user):
    user = db.session.merge(test_user)
    sm = INTERVENTION.SELF_MANAGEMENT
    sr = INTERVENTION.SEXUAL_RECOVERY

    sm.public_access = False
    sr.public_access = False
    d = {
        'function': 'combine_strategies',
        'kwargs': [
            {'name': 'strategy_1',
             'value': 'allow_if_not_in_intervention'},
            {'name': 'strategy_1_kwargs',
             'value': [{
                 'name': 'intervention_name',
                 'value': INTERVENTION.SEXUAL_RECOVERY.name}]},
            {'name': 'strategy_2',
             'value': 'not_in_role_list'},
            {'name': 'strategy_2_kwargs',
             'value': [{
                 'name': 'role_list',
                 'value': [ROLE.WRITE_ONLY.value]}]}
        ]
    }

    with SessionScope(db):
        strat = AccessStrategy(
            name="SELF_MANAGEMENT if not SR and not in WRITE_ONLY",
            intervention_id=sm.id,
            function_details=json.dumps(d))
        db.session.add(strat)
        db.session.commit()
    user, sm, sr = map(db.session.merge, (user, sm, sr))

    # Prior to granting user WRITE_ONLY role, the strategy
    # should give access to p3p
    assert sm.display_for_user(user).access
    assert sm.quick_access_check(user)

    # Add WRITE_ONLY to user's roles
    add_role(user, ROLE.WRITE_ONLY.value)
    with SessionScope(db):
        db.session.commit()
    user, sm, sr = map(db.session.merge, (user, sm, sr))
    assert not sm.display_for_user(user).access
    assert not sm.quick_access_check(user)

    # Revert role change for next condition
    user.roles = []
    with SessionScope(db):
        db.session.commit()
    user, sm, sr = map(db.session.merge, (user, sm, sr))
    assert sm.display_for_user(user).access
    assert sm.quick_access_check(user)

    # Grant user sr access, they should lose sm visibility
    ui = UserIntervention(
        user_id=user.id,
        intervention_id=INTERVENTION.SEXUAL_RECOVERY.id,
        access='granted')
    with SessionScope(db):
        db.session.add(ui)
        db.session.commit()
    user, sm, sr = map(db.session.merge, (user, sm, sr))
    assert not sm.display_for_user(user).access
    assert not sm.quick_access_check(user)


def test_in_role(initialize_static, test_user):
    user = db.session.merge(test_user)
    sm = INTERVENTION.SELF_MANAGEMENT
    sm.public_access = False
    d = {
        'function': 'in_role_list',
        'kwargs': [
            {'name': 'role_list',
             'value': [ROLE.PATIENT.value]}]
    }

    with SessionScope(db):
        strat = AccessStrategy(
            name="SELF_MANAGEMENT if PATIENT",
            intervention_id=sm.id,
            function_details=json.dumps(d))
        db.session.add(strat)
        db.session.commit()
    user, sm = map(db.session.merge, (user, sm))

    # Prior to granting user PATIENT role, the strategy
    # should not give access to SM
    assert not sm.display_for_user(user).access
    assert not sm.quick_access_check(user)

    # Add PATIENT to user's roles
    add_role(user, ROLE.PATIENT.value)
    with SessionScope(db):
        db.session.commit()
    user, sm = map(db.session.merge, (user, sm))
    assert sm.display_for_user(user).access
    assert sm.quick_access_check(user)


def test_card_html_update(
        client, initialize_static, initialized_patient_logged_in):
    """Confirm assessment status state affects AE card on /home view"""
    test_user = initialized_patient_logged_in
    test_user_id = test_user.id

    # Need a current date, adjusted slightly to test UTC boundary
    # date rendering, one day back so the assessment period will have
    # started.
    dt = datetime.utcnow().replace(
        hour=20, minute=0, second=0, microsecond=0) - relativedelta(
        days=1)

    # generate questionnaire banks and associate user with
    # metastatic organization
    mock_questionnairebanks('eproms')
    metastatic_org = Organization.query.filter_by(name='metastatic').one()
    test_user = db.session.merge(test_user)
    test_user.organizations.append(metastatic_org)
    consent = UserConsent.query.filter(
        UserConsent.user_id == test_user_id).one()
    consent.organization_id = metastatic_org.id
    consent.acceptance_date = dt

    # Fetch home page, which should include Assessment Engine "card"
    results = client.get("/home")

    # without completing an assessment, card_html should include username
    assert bytes(test_user.display_name, 'utf-8') in results.data

    # Add a fake assessments and see a change
    m_qb = QuestionnaireBank.query.filter(
        QuestionnaireBank.name == 'metastatic').filter(
        QuestionnaireBank.classification == 'baseline').one()
    for i in metastatic_baseline_instruments:
        mock_qr(instrument_id=i, timestamp=dt, qb=m_qb)
    mi_qb = QuestionnaireBank.query.filter_by(
        name='metastatic_indefinite').first()
    mock_qr(instrument_id='irondemog', timestamp=dt, qb=mi_qb)

    invalidate_users_QBT(test_user_id, research_study_id='all')

    results = client.get("/home")
    assert bytes("Thank you", 'utf-8') in results.data

    ae = INTERVENTION.ASSESSMENT_ENGINE
    assert ae.quick_access_check(test_user)

    # test datetime display based on user timezone
    today = datetime.strftime(dt, '%e %b %Y')
    assert bytes(today, 'utf-8') in results.data
    test_user = db.session.merge(test_user)
    test_user.timezone = "Asia/Tokyo"
    with SessionScope(db):
        db.session.commit()
    tomorrow = datetime.strftime(
        dt + timedelta(days=1), '%e %b %Y')
    results = client.get("/home")
    assert bytes(tomorrow, 'utf-8') in results.data


def test_expired(client, initialized_patient_logged_in):
    """If baseline expired check message"""
    test_user = initialized_patient_logged_in

    # backdate so baseline is expired
    backdate, nowish = associative_backdate(
        now=datetime.utcnow(), backdate=relativedelta(months=3))

    # generate questionnaire banks; associate and consent user with
    # localized organization
    mock_questionnairebanks('eproms')
    localized_org = Organization.query.filter_by(name='localized').one()
    test_user = db.session.merge(test_user)
    test_user.organizations.append(localized_org)
    consent = UserConsent.query.filter(
        UserConsent.user_id == test_user.id).one()
    consent.organization_id = localized_org.id
    consent.acceptance_date = backdate

    results = client.get("/home")
    assert bytes(
        "The assessment is no longer available", 'utf-8') in results.data


def test_strat_from_json(initialize_static):
    """Create access strategy from json"""
    d = {
        'name': 'unit test example',
        'description': 'a lovely way to test',
        'function_details': {
            'function': 'allow_if_not_in_intervention',
            'kwargs': [{'name': 'intervention_name',
                        'value': INTERVENTION.SELF_MANAGEMENT.name}]
        }
    }
    acc_strat = AccessStrategy.from_json(d)
    assert d['name'] == acc_strat.name
    assert d['function_details'] == json.loads(acc_strat.function_details)


def test_strat_view(admin_user, login, client, deepen_org_tree):
    """Test strategy view functions"""
    login()
    d = {
        'name': 'unit test example',
        'function_details': {
            'function': 'allow_if_not_in_intervention',
            'kwargs': [{'name': 'intervention_name',
                        'value': INTERVENTION.SELF_MANAGEMENT.name}]
        }
    }
    response = client.post(
        '/api/intervention/sexual_recovery/access_rule',
        content_type='application/json',
        data=json.dumps(d))
    assert response.status_code == 200

    # fetch it back and compare
    response = (client
                .get('/api/intervention/sexual_recovery/access_rule'))
    assert response.status_code == 200
    data = response.json
    assert len(data['rules']) == 1
    assert d['name'] == data['rules'][0]['name']
    assert d['function_details'] == data['rules'][0]['function_details']


def test_strat_dup_rank(admin_user, login, client, deepen_org_tree):
    """Rank must be unique"""
    login()
    d = {
        'name': 'unit test example',
        'rank': 1,
        'function_details': {
            'function': 'allow_if_not_in_intervention',
            'kwargs': [{'name': 'intervention_name',
                        'value': INTERVENTION.SELF_MANAGEMENT.name}]
        }
    }
    response = client.post(
        '/api/intervention/sexual_recovery/access_rule',
        content_type='application/json',
        data=json.dumps(d))
    assert response.status_code == 200
    d = {
        'name': 'unit test same rank example',
        'rank': 1,
        'description': 'should not take with same rank',
        'function_details': {
            'function': 'allow_if_not_in_intervention',
            'kwargs': [{'name': 'intervention_name',
                        'value': INTERVENTION.SELF_MANAGEMENT.name}]
        }
    }
    response = client.post(
        '/api/intervention/sexual_recovery/access_rule',
        content_type='application/json',
        data=json.dumps(d))
    assert response.status_code == 400


def test_and_strats(initialize_static, test_user):
    # Create a logical 'and' with multiple strategies

    ds_p3p = INTERVENTION.DECISION_SUPPORT_P3P
    ds_p3p.public_access = False
    user = db.session.merge(test_user)
    identifier = Identifier(
        value='decision_support_p3p', system=DECISION_SUPPORT_GROUP)
    uw = Organization(name='UW Medicine (University of Washington)')
    uw.identifiers.append(identifier)
    INTERVENTION.SEXUAL_RECOVERY.public_access = False
    with SessionScope(db):
        db.session.add(uw)
        db.session.commit()
    user, uw = map(db.session.merge, (user, uw))
    uw_child = Organization(name='UW clinic', partOf_id=uw.id)
    with SessionScope(db):
        db.session.add(uw_child)
        db.session.commit()
    user, uw, uw_child = map(db.session.merge, (user, uw, uw_child))

    d = {
        'name': 'not in SR _and_ in clinc UW',
        'function': 'combine_strategies',
        'kwargs': [
            {'name': 'strategy_1',
             'value': 'allow_if_not_in_intervention'},
            {'name': 'strategy_1_kwargs',
             'value': [{'name': 'intervention_name',
                        'value': INTERVENTION.SEXUAL_RECOVERY.name}]},
            {'name': 'strategy_2',
             'value': 'limit_by_clinic_w_id'},
            {'name': 'strategy_2_kwargs',
             'value': [{'name': 'identifier_value',
                        'value': 'decision_support_p3p'}]}
        ]
    }
    with SessionScope(db):
        strat = AccessStrategy(
            name=d['name'],
            intervention_id=INTERVENTION.DECISION_SUPPORT_P3P.id,
            function_details=json.dumps(d))
        db.session.add(strat)
        db.session.commit()
    user, ds_p3p = map(db.session.merge, (user, ds_p3p))

    # first strat true, second false.  therfore, should be False
    assert not ds_p3p.display_for_user(user).access

    # Add the child organization to the user, which should be included
    # due to default behavior of limit_by_clinic_w_id
    user.organizations.append(uw_child)
    with SessionScope(db):
        db.session.commit()
    user, ds_p3p = map(db.session.merge, (user, ds_p3p))
    # first strat true, second true.  therfore, should be True
    assert ds_p3p.display_for_user(user).access

    ui = UserIntervention(
        user_id=user.id,
        intervention_id=INTERVENTION.SEXUAL_RECOVERY.id,
        access='granted')
    with SessionScope(db):
        db.session.add(ui)
        db.session.commit()
    user, ds_p3p = map(db.session.merge, (user, ds_p3p))

    # first strat true, second false.  AND should be false
    assert not ds_p3p.display_for_user(user).access


def test_p3p_conditions(
        test_user, add_procedure, login, deepen_org_tree):
    # Test the list of conditions expected for p3p
    ds_p3p = INTERVENTION.DECISION_SUPPORT_P3P
    ds_p3p.public_access = False
    user = db.session.merge(test_user)
    p3p_identifier = Identifier(
        value='decision_support_p3p', system=DECISION_SUPPORT_GROUP)
    wc_identifier = Identifier(
        value='decision_support_wisercare', system=DECISION_SUPPORT_GROUP)
    ucsf = Organization(name='UCSF Medical Center')
    uw = Organization(
        name='UW Medicine (University of Washington)')
    ucsf.identifiers.append(wc_identifier)
    uw.identifiers.append(p3p_identifier)
    with SessionScope(db):
        db.session.add(ucsf)
        db.session.add(uw)
        db.session.commit()
    user = db.session.merge(user)
    user.organizations.append(ucsf)
    user.organizations.append(uw)
    INTERVENTION.SEXUAL_RECOVERY.public_access = False
    with SessionScope(db):
        db.session.commit()
    ucsf, user, uw = map(db.session.merge, (ucsf, user, uw))

    # Full logic from story #127433167
    description = (
        "[strategy_1: (user NOT IN sexual_recovery)] "
        "AND [strategy_2 <a nested combined strategy>: "
        "((user NOT IN list of clinics (including UCSF)) OR "
        "(user IN list of clinics including UCSF and UW))] "
        "AND [strategy_3: (user has NOT started TX)] "
        "AND [strategy_4: (user does NOT have PCaMETASTASIZE)]")

    d = {
        'function': 'combine_strategies',
        'kwargs': [
            # Not in SR (strat 1)
            {'name': 'strategy_1',
             'value': 'allow_if_not_in_intervention'},
            {'name': 'strategy_1_kwargs',
             'value': [{'name': 'intervention_name',
                        'value': INTERVENTION.SEXUAL_RECOVERY.name}]},
            # Not in clinic list (UCSF,) OR (In Clinic UW and UCSF) (#2)
            {'name': 'strategy_2',
             'value': 'combine_strategies'},
            {'name': 'strategy_2_kwargs',
             'value': [
                 {'name': 'combinator',
                  'value': 'any'},  # makes this combination an 'OR'
                 {'name': 'strategy_1',
                  'value': 'not_in_clinic_w_id'},
                 {'name': 'strategy_1_kwargs',
                  'value': [{'name': 'identifier_value',
                             'value': 'decision_support_wisercare'}]},
                 {'name': 'strategy_2',
                  'value': 'limit_by_clinic_w_id'},
                 {'name': 'strategy_2_kwargs',
                  'value': [{'name': 'identifier_value',
                             'value': 'decision_support_p3p'}]},
             ]},
            # Not Started TX (strat 3)
            {'name': 'strategy_3',
             'value': 'tx_begun'},
            {'name': 'strategy_3_kwargs',
             'value': [{'name': 'boolean_value', 'value': 'false'}]},
            # Has Localized PCa (strat 4)
            {'name': 'strategy_4',
             'value': 'observation_check'},
            {'name': 'strategy_4_kwargs',
             'value': [{'name': 'display',
                        'value': CC.PCaLocalized.codings[0].display},
                       {'name': 'boolean_value', 'value': 'true'}]},
        ]
    }
    with SessionScope(db):
        strat = AccessStrategy(
            name='P3P Access Conditions',
            description=description,
            intervention_id=INTERVENTION.DECISION_SUPPORT_P3P.id,
            function_details=json.dumps(d))
        db.session.add(strat)
        db.session.commit()
    user, ds_p3p = map(db.session.merge, (user, ds_p3p))

    # only first two strats true so far, therfore, should be False
    assert not ds_p3p.display_for_user(user).access

    add_procedure(
        code='424313000', display='Started active surveillance')
    user = db.session.merge(user)
    login()
    user.save_observation(
        codeable_concept=CC.PCaLocalized, value_quantity=CC.TRUE_VALUE,
        audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
        status='preliminary', issued=None)
    with SessionScope(db):
        db.session.commit()
    user, ds_p3p = map(db.session.merge, (user, ds_p3p))

    # All conditions now met, should have access
    assert ds_p3p.display_for_user(user).access

    # Remove all clinics, should still have access
    user.organizations = []
    with SessionScope(db):
        db.session.commit()
    user, ds_p3p = map(db.session.merge, (user, ds_p3p))
    assert len(user.organizations) == 0
    assert ds_p3p.display_for_user(user).access


def test_eproms_p3p_conditions(
        test_user, add_procedure, login, deepen_org_tree):
    # Test the list of conditions expected for p3p on eproms
    # very similar to truenth p3p, plus ! role write_only
    ds_p3p = INTERVENTION.DECISION_SUPPORT_P3P
    ds_p3p.public_access = False
    user = db.session.merge(test_user)
    p3p_identifier = Identifier(
        value='decision_support_p3p', system=DECISION_SUPPORT_GROUP)
    wc_identifier = Identifier(
        value='decision_support_wisercare', system=DECISION_SUPPORT_GROUP)
    ucsf = Organization(name='UCSF Medical Center')
    uw = Organization(
        name='UW Medicine (University of Washington)')
    ucsf.identifiers.append(wc_identifier)
    uw.identifiers.append(p3p_identifier)
    with SessionScope(db):
        db.session.add(ucsf)
        db.session.add(uw)
        db.session.commit()
    user = db.session.merge(user)
    user.organizations.append(ucsf)
    user.organizations.append(uw)
    INTERVENTION.SEXUAL_RECOVERY.public_access = False
    with SessionScope(db):
        db.session.commit()
    ucsf, user, uw = map(db.session.merge, (ucsf, user, uw))

    # Full logic from story #127433167
    description = (
        "[strategy_1: (user NOT IN sexual_recovery)] "
        "AND [strategy_2 <a nested combined strategy>: "
        "((user NOT IN list of clinics (including UCSF)) OR "
        "(user IN list of clinics including UCSF and UW))] "
        "AND [strategy_3: (user has NOT started TX)] "
        "AND [strategy_4: (user does NOT have PCaMETASTASIZE)] "
        "AND [startegy_5: (user does NOT have roll WRITE_ONLY)]")

    d = {
        'function': 'combine_strategies',
        'kwargs': [
            # Not in SR (strat 1)
            {'name': 'strategy_1',
             'value': 'allow_if_not_in_intervention'},
            {'name': 'strategy_1_kwargs',
             'value': [{'name': 'intervention_name',
                        'value': INTERVENTION.SEXUAL_RECOVERY.name}]},
            # Not in clinic list (UCSF,) OR (In Clinic UW and UCSF) (#2)
            {'name': 'strategy_2',
             'value': 'combine_strategies'},
            {'name': 'strategy_2_kwargs',
             'value': [
                 {'name': 'combinator',
                  'value': 'any'},  # makes this combination an 'OR'
                 {'name': 'strategy_1',
                  'value': 'not_in_clinic_w_id'},
                 {'name': 'strategy_1_kwargs',
                  'value': [{'name': 'identifier_value',
                             'value': 'decision_support_wisercare'}]},
                 {'name': 'strategy_2',
                  'value': 'combine_strategies'},
                 {'name': 'strategy_2_kwargs',
                  'value': [
                      {'name': 'strategy_1',
                       'value': 'limit_by_clinic_w_id'},
                      {'name': 'strategy_1_kwargs',
                       'value': [{'name': 'identifier_value',
                                  'value': 'decision_support_wisercare'}]},
                      {'name': 'strategy_2',
                       'value': 'limit_by_clinic_w_id'},
                      {'name': 'strategy_2_kwargs',
                       'value': [{'name': 'identifier_value',
                                  'value': 'decision_support_p3p'}]},
                  ]},
             ]},
            # Not Started TX (strat 3)
            {'name': 'strategy_3',
             'value': 'tx_begun'},
            {'name': 'strategy_3_kwargs',
             'value': [{'name': 'boolean_value', 'value': 'false'}]},
            # Has Localized PCa (strat 4)
            {'name': 'strategy_4',
             'value': 'observation_check'},
            {'name': 'strategy_4_kwargs',
             'value': [{'name': 'display',
                        'value': CC.PCaLocalized.codings[0].display},
                       {'name': 'boolean_value', 'value': 'true'}]},
            # Does NOT have roll WRITE_ONLY (strat 5)
            {'name': 'strategy_5',
             'value': 'not_in_role_list'},
            {'name': 'strategy_5_kwargs',
             'value': [{'name': 'role_list',
                        'value': [ROLE.WRITE_ONLY.value]}]}
        ]
    }
    with SessionScope(db):
        strat = AccessStrategy(
            name='P3P Access Conditions',
            description=description,
            intervention_id=INTERVENTION.DECISION_SUPPORT_P3P.id,
            function_details=json.dumps(d))
        db.session.add(strat)
        db.session.commit()
    user, ds_p3p = map(db.session.merge, (user, ds_p3p))

    # only first two strats true so far, therfore, should be False
    assert not ds_p3p.display_for_user(user).access

    add_procedure(
        code='424313000', display='Started active surveillance')
    user = db.session.merge(user)
    login()
    user.save_observation(
        codeable_concept=CC.PCaLocalized, value_quantity=CC.TRUE_VALUE,
        audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
        status='final', issued=None)
    with SessionScope(db):
        db.session.commit()
    user, ds_p3p = map(db.session.merge, (user, ds_p3p))

    # All conditions now met, should have access
    assert ds_p3p.display_for_user(user).access

    # Remove all clinics, should still have access
    user.organizations = []
    with SessionScope(db):
        db.session.commit()
    user, ds_p3p = map(db.session.merge, (user, ds_p3p))
    assert len(user.organizations) == 0
    assert ds_p3p.display_for_user(user).access

    # Finally, add the WRITE_ONLY group and it should disappear
    add_role(user, ROLE.WRITE_ONLY.value)
    with SessionScope(db):
        db.session.commit()
    user, ds_p3p = map(db.session.merge, (user, ds_p3p))
    assert not ds_p3p.display_for_user(user).access


def test_truenth_st_conditions(
        initialize_static, test_user,
        add_procedure, login, deepen_org_tree):
    # Test the list of conditions expected for SymptomTracker in truenth
    sm = INTERVENTION.SELF_MANAGEMENT
    sm.public_access = False
    user = db.session.merge(test_user)
    add_role(user, ROLE.PATIENT.value)
    sm_identifier = Identifier(
        value='self_management', system=DECISION_SUPPORT_GROUP)
    uw = Organization(
        name='UW Medicine (University of Washington)')
    uw.identifiers.append(sm_identifier)
    with SessionScope(db):
        db.session.add(uw)
        db.session.commit()
    user = db.session.merge(user)
    user.organizations.append(uw)
    INTERVENTION.SEXUAL_RECOVERY.public_access = False
    with SessionScope(db):
        db.session.add(user)
        db.session.commit()
    user, uw = map(db.session.merge, (user, uw))

    # Full logic from story #150532380
    description = (
        "[strategy_1: (user NOT IN sexual_recovery)] "
        "AND [strategy_2: (user has role PATIENT)] "
        "AND [strategy_3: (user has BIOPSY)]")

    d = {
        'function': 'combine_strategies',
        'kwargs': [
            # Not in SR (strat 1)
            {'name': 'strategy_1',
             'value': 'allow_if_not_in_intervention'},
            {'name': 'strategy_1_kwargs',
             'value': [{'name': 'intervention_name',
                        'value': INTERVENTION.SEXUAL_RECOVERY.name}]},
            # Does has role PATIENT (strat 2)
            {'name': 'strategy_2',
             'value': 'in_role_list'},
            {'name': 'strategy_2_kwargs',
             'value': [{'name': 'role_list',
                        'value': [ROLE.PATIENT.value]}]},
            # Has Localized PCa (strat 3)
            {'name': 'strategy_3',
             'value': 'observation_check'},
            {'name': 'strategy_3_kwargs',
             'value': [{'name': 'display',
                        'value': CC.BIOPSY.codings[0].display},
                       {'name': 'boolean_value', 'value': 'true'}]}
        ]
    }
    with SessionScope(db):
        strat = AccessStrategy(
            name='Symptom Tracker Conditions',
            description=description,
            intervention_id=INTERVENTION.SELF_MANAGEMENT.id,
            function_details=json.dumps(d))
        db.session.add(strat)
        db.session.commit()
    user, sm = map(db.session.merge, (user, sm))

    # only first two strats true so far, therfore, should be False
    assert not sm.display_for_user(user).access

    add_procedure(
        code='424313000', display='Started active surveillance')
    user = db.session.merge(user)
    login()
    user.save_observation(
        codeable_concept=CC.BIOPSY, value_quantity=CC.TRUE_VALUE,
        audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
        status='unknown', issued=None)
    with SessionScope(db):
        db.session.commit()
    user, sm = map(db.session.merge, (user, sm))

    # All conditions now met, should have access
    assert sm.display_for_user(user).access

    # Remove all clinics, should still have access
    user.organizations = []
    with SessionScope(db):
        db.session.commit()
    user, sm = map(db.session.merge, (user, sm))
    assert len(user.organizations) == 0
    assert sm.display_for_user(user).access

    # Finally, remove the PATIENT role and it should disappear
    user.roles.pop()
    with SessionScope(db):
        db.session.add(user)
        db.session.commit()
    user, sm = map(db.session.merge, (user, sm))
    assert not sm.display_for_user(user).access


def test_get_empty_user_intervention(
        test_user_login, client, deepen_org_tree):
    # Get on user w/o user_intervention
    response = client.get('/api/intervention/{i}/user/{u}'.format(
        i=INTERVENTION.SELF_MANAGEMENT.name, u=TEST_USER_ID))
    assert response.status_code == 200
    assert len(response.json.keys()) == 1
    assert response.json['user_id'] == TEST_USER_ID


def test_get_user_intervention(
        initialize_static, test_user,
        login, client, deepen_org_tree):
    intervention_id = INTERVENTION.SEXUAL_RECOVERY.id
    ui = UserIntervention(intervention_id=intervention_id,
                          user_id=TEST_USER_ID,
                          access='granted',
                          card_html='custom ch',
                          link_label='link magic',
                          link_url='http://example.com',
                          status_text='status example',
                          staff_html='custom ph')
    with SessionScope(db):
        db.session.add(ui)
        db.session.commit()

    login()
    response = client.get('/api/intervention/{i}/user/{u}'.format(
        i=INTERVENTION.SEXUAL_RECOVERY.name, u=TEST_USER_ID))
    assert response.status_code == 200
    assert len(response.json.keys()) == 7
    assert response.json['user_id'] == TEST_USER_ID
    assert response.json['access'] == 'granted'
    assert response.json['card_html'] == "custom ch"
    assert response.json['link_label'] == "link magic"
    assert response.json['link_url'] == "http://example.com"
    assert response.json['status_text'] == "status example"
    assert response.json['staff_html'] == "custom ph"


def test_communicate(add_user, login, client, deepen_org_tree):
    email_group = Group(name='test_email')
    foo = add_user(username='foo@example.com')
    boo = add_user(username='boo@example.com')
    foo, boo = map(db.session.merge, (foo, boo))
    foo.groups.append(email_group)
    boo.groups.append(email_group)
    data = {
        'protocol': 'email',
        'group_name': 'test_email',
        'subject': "Just a test, ignore",
        'message':
            'Review results at <a href="http://www.example.com">here</a>'
    }
    login()
    response = client.post('/api/intervention/{}/communicate'.format(
        INTERVENTION.DECISION_SUPPORT_P3P.name),
        content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 200
    assert response.json['message'] == 'sent'

    message = EmailMessage.query.one()
    set1 = {foo.email, boo.email}
    set2 = set(message.recipients.split())
    assert set1 == set2


def test_dynamic_intervention_access():
    # Confirm interventions dynamically added still accessible
    newbee = Intervention(
        name='newbee', description='test', subscribed_events=0)
    with SessionScope(db):
        db.session.add(newbee)
        db.session.commit()

    assert INTERVENTION.newbee == db.session.merge(newbee)


def test_bogus_intervention_access(
        test_user, login, promote_user, client, deepen_org_tree):
    with pytest.raises(AttributeError):
        INTERVENTION.phoney

    login()
    promote_user(role_name=ROLE.SERVICE.value)
    data = {'user_id': TEST_USER_ID, 'access': "granted"}
    response = client.put('/api/intervention/phoney', data=data)
    assert response.status_code == 404


@pytest.fixture
def setUp(initialize_static):

    from portal.config.model_persistence import ModelPersistence
    from portal.config.site_persistence import models
    from portal.models.coding import Coding
    from portal.models.research_protocol import ResearchProtocol

    eproms_config_dir = os.path.join(
        os.path.dirname(__file__), "../portal/config/eproms")

    # Load minimal set of persistence files for access_strategy, in same
    # order defined in site_persistence
    needed = {
        ResearchStudy,
        ResearchProtocol,
        Coding,
        Organization,
        AccessStrategy,
        Intervention}

    for model in models:
        if model.cls not in needed:
            continue
        mp = ModelPersistence(
            model_class=model.cls, sequence_name=model.sequence_name,
            lookup_field=model.lookup_field, target_dir=eproms_config_dir)
        mp.import_(keep_unmentioned=False)


def test_self_mgmt(setUp, patient_user, test_user):
    """Patient w/ Southampton org should get access to self_mgmt"""
    southampton = Organization.query.filter_by(name='Southampton').one()
    test_user = db.session.merge(test_user)
    test_user.organizations.append(southampton)
    self_mgmt = Intervention.query.filter_by(name='self_management').one()
    assert self_mgmt.quick_access_check(test_user)


def test_self_mgmt_user_denied(setUp, test_user):
    """Non-patient w/ Southampton org should NOT get self_mgmt access"""
    southampton = Organization.query.filter_by(name='Southampton').one()
    test_user.organizations.append(southampton)
    self_mgmt = Intervention.query.filter_by(name='self_management').one()
    assert not self_mgmt.quick_access_check(test_user)


def test_self_mgmt_org_denied(setUp, patient_user, test_user):
    """Patient w/o Southampton org should NOT get self_mgmt access"""
    self_mgmt = Intervention.query.filter_by(name='self_management').one()
    user = db.session.merge(test_user)
    assert not self_mgmt.quick_access_check(user)
