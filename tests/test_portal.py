"""Unit test module for portal views"""

from datetime import datetime
import tempfile
import urllib

from flask_swagger import swagger
from flask_webtest import SessionScope
import pytest
from swagger_spec_validator import validate_spec_url

from portal.config.config import TestConfig
from portal.extensions import db
from portal.factories.app import create_app
from portal.models.intervention import INTERVENTION, UserIntervention
from portal.models.message import EmailMessage
from portal.models.organization import Organization
from portal.models.role import ROLE
from portal.models.user import User, get_user
from tests import OAUTH_INFO_PROVIDER_LOGIN, TEST_USER_ID


def test_card_html(
        test_client, test_user_login, required_clinical_data,
        bless_with_basics_no_patient_role, client):
    """Interventions can customize the button text """
    intervention = INTERVENTION.DECISION_SUPPORT_P3P
    intervention.public_access = True  # make the card avail for the test
    test_client = db.session.merge(test_client)
    test_client.intervention = intervention
    intervention.card_html = "Custom Label"

    response = client.get('/home')
    assert response.status_code == 200

    assert 'Custom Label' in response.get_data(as_text=True)
    intervention = db.session.merge(intervention)
    assert intervention.card_html in response.get_data(as_text=True)


def test_user_card_html(
        test_client, test_user_login,
        required_clinical_data,
        bless_with_basics_no_patient_role, client):
    """Interventions can further customize per user"""
    intervention = INTERVENTION.DECISION_SUPPORT_P3P
    intervention.public_access = True  # make the card avail for the test
    test_client = db.session.merge(test_client)
    test_client.intervention = intervention
    ui = UserIntervention(
        user_id=TEST_USER_ID, intervention_id=intervention.id)
    ui.card_html = "<b>Bold Card Text</b>"
    ui.link_label = "Custom User Label"
    ui.link_url = 'http://example.com/?test=param1'
    with SessionScope(db):
        db.session.add(ui)
        db.session.commit()

    user = User.query.get(TEST_USER_ID)

    response = client.get('/home')
    assert response.status_code == 200

    ui = db.session.merge(ui)
    assert ui.card_html in response.get_data(as_text=True)
    assert ui.link_label in response.get_data(as_text=True)
    assert ui.link_url in response.get_data(as_text=True)
    intervention = db.session.merge(intervention)
    assert (
        intervention.display_for_user(user).link_label
        in response.get_data(as_text=True))


def test_staff_html(
        test_client, bless_with_basics,
        test_user_login, promote_user, app, client):
    """Interventions can customize the staff text """
    intervention = INTERVENTION.sexual_recovery
    test_client = db.session.merge(test_client)
    test_client.intervention = intervention
    ui = UserIntervention(
        user_id=TEST_USER_ID,
        intervention_id=intervention.id)
    ui.staff_html = "Custom text for <i>staff</i>"
    with SessionScope(db):
        db.session.add(ui)
        db.session.commit()

    promote_user(role_name=ROLE.INTERVENTION_STAFF.value)

    # This test requires PATIENT_LIST_ADDL_FIELDS includes the
    # 'reports' field
    app.config['PATIENT_LIST_ADDL_FIELDS'] = ['reports']
    response = client.get('/patients/')

    ui = db.session.merge(ui)
    results = response.get_data(as_text=True)
    assert ui.staff_html in results


def test_public_access(
        test_client, test_user_login,
        required_clinical_data, bless_with_basics, client):
    """Interventions w/o public access should be hidden"""
    intervention = INTERVENTION.sexual_recovery
    test_client = db.session.merge(test_client)
    test_client.intervention = intervention
    intervention.public_access = False

    response = client.get('/home')

    assert 'Sexual Recovery' not in response.get_data(as_text=True)

    # now give just the test user access
    intervention = db.session.merge(intervention)
    ui = UserIntervention(
        user_id=TEST_USER_ID,
        intervention_id=intervention.id,
        access="granted")
    with SessionScope(db):
        db.session.add(ui)
        db.session.commit()
    response = client.get('/home')

    assert 'Sexual Recovery' in response.get_data(as_text=True)


def test_admin_list(add_user, promote_user, test_user_login, client):
    """Test admin view lists all users"""
    # Generate a few users with a smattering of roles
    u1 = add_user(username='u1@foo.bar')
    u2 = add_user(username='u2@bar.foo')
    promote_user(u1, role_name=ROLE.ADMIN.value)
    promote_user(u2, role_name=ROLE.APPLICATION_DEVELOPER.value)

    # Test user needs admin role to view list
    promote_user(role_name=ROLE.ADMIN.value)
    response = client.get('/admin')

    # Should at least see an entry per user in system
    assert (response.get_data(as_text=True).count('/profile')
            >= User.query.count())


def test_invite(test_user_login, client):
    """Test email invite form"""
    test_user = User.query.get(TEST_USER_ID)
    test_user.email = 'test_user@uw.edu'
    db.session.add(test_user)
    db.session.commit()

    postdata = {
        'subject': 'unittest subject',
        'recipients': 'test_user@yahoo.com test_user@uw.edu',
        'body': "Ode to joy"}
    response = client.post('/invite', data=postdata,
                           follow_redirects=True)
    assert "Email Invite Sent" in response.get_data(as_text=True)


def test_message_sent(test_user_login, client):
    """Email invites - test view for sent messages"""
    sent_at = datetime.strptime(
        "2000/01/01 12:31:00", "%Y/%m/%d %H:%M:%S")
    message = EmailMessage(
        subject='a subject', user_id=TEST_USER_ID,
        sender="testuser@email.com",
        body='Welcome to testing \u2713',
        sent_at=sent_at,
        recipients="one@ex1.com two@two.org")
    db.session.add(message)
    db.session.commit()

    # confirm styling unicode functions
    body = message.style_message(message.body)
    assert 'DOCTYPE' in body
    assert 'style' in body
    assert isinstance(body, str)

    response = client.get('/invite/{0}'.format(message.id))
    assert (response.get_data(as_text=True).find(
        sent_at.strftime('%m/%d/%Y %H:%M:%S')) > 0)
    assert (response.get_data(as_text=True).find('one@ex1.com two@two.org')
            > 0)


def test_missing_message(test_user_login, client):
    """Request to view non existant message should 404"""
    response = client.get('/invite/404')
    assert response.status_code == 404


def test_swagger_docgen(client):
    """Build swagger docs for entire project"""

    expected_keys = (
        'info',
        'paths',
        'swagger',
        'definitions',
    )
    swag = swagger(client.application)

    for key in expected_keys:
        assert key in swag


def test_swagger_validation(client):
    """Ensure our swagger spec matches swagger schema"""

    with tempfile.NamedTemporaryFile(
        prefix='swagger_test_',
        suffix='.json',
        delete=True,
    ) as temp_spec:
        temp_spec.write(client.get('/spec').data)
        temp_spec.seek(0)

        validate_spec_url("file:%s" % temp_spec.name)


def test_report_error(test_user_login, client):
    params = {
        'subject_id': 112,
        'page_url': '/not/real',
        'message': 'creative test string'
    }
    response = client.get('/report-error?{}'.format(
        urllib.parse.urlencode(params)))
    assert response.status_code == 200


def test_configuration_settings(test_user_login, app, client):
    lr_group = app.config['LR_GROUP']
    response = client.get('/api/settings/lr_group')
    assert response.status_code == 200
    assert response.json.get('LR_GROUP') == lr_group
    response2 = client.get('/api/settings/bad_value')
    assert response2.status_code == 400


def test_configuration_secrets(client):
    """Ensure config keys containing secrets are not exposed"""
    blacklist = (
        'SECRET',
        'URI',
        'SQL',
    )
    response = client.get('/api/settings')

    assert response.status_code == 200
    assert not any(
        any(k in config_key for k in blacklist)
        for config_key in response.json
    )


@pytest.fixture
def eproms_app():
    """
    Overload base version to hide the GIL (allows registration of ePROMs)
    """
    tc = TestConfig()
    setattr(tc, 'HIDE_GIL', True)
    app = create_app(tc)
    return app


def test_redirect_validation_website_consent(
        promote_user, login, test_client,
        eproms_app, client):
    promote_user(role_name=ROLE.ADMIN.value)
    promote_user(role_name=ROLE.STAFF.value)

    org = Organization(name='test org')
    user = get_user(TEST_USER_ID)
    with SessionScope(db):
        db.session.add(org)
        user.organizations.append(org)
        db.session.commit()

    login()

    test_client = db.session.merge(test_client)
    client_url = test_client._redirect_uris
    local_url = "http://{}/home?test".format(
        eproms_app.config.get('SERVER_NAME'))
    invalid_url = 'http://invalid.org'

    # validate redirect of /website-consent-script GET
    response = client.get(
        '/website-consent-script/{}'.format(TEST_USER_ID),
        query_string={'redirect_url': local_url}
    )
    assert response.status_code == 200

    response2 = client.get(
        '/website-consent-script/{}'.format(TEST_USER_ID),
        query_string={'redirect_url': invalid_url}
    )
    assert response2.status_code == 401


def test_redirect_validation_session_login_valid_url(
        promote_user, login, test_client,
        eproms_app, client):
    promote_user(role_name=ROLE.ADMIN.value)
    promote_user(role_name=ROLE.STAFF.value)

    org = Organization(name='test org')
    user = get_user(TEST_USER_ID)
    with SessionScope(db):
        db.session.add(org)
        user.organizations.append(org)
        db.session.commit()

    test_client = db.session.merge(test_client)
    client_url = test_client._redirect_uris
    local_url = "http://{}/home?test".format(
        eproms_app.config.get('SERVER_NAME'))
    invalid_url = 'http://invalid.org'

    # validate session login redirect with valid url
    oauth_info = {
        'user_id': TEST_USER_ID,
        'next': client_url,
    }
    response3 = login(oauth_info=oauth_info)
    assert response3.status_code == 200


def test_redirect_validation_session_login_invalid_url(
        promote_user, login, test_client,
        eproms_app, client):
    promote_user(role_name=ROLE.ADMIN.value)
    promote_user(role_name=ROLE.STAFF.value)

    org = Organization(name='test org')
    user = get_user(TEST_USER_ID)
    with SessionScope(db):
        db.session.add(org)
        user.organizations.append(org)
        db.session.commit()

    test_client = db.session.merge(test_client)
    client_url = test_client._redirect_uris
    local_url = "http://{}/home?test".format(
        eproms_app.config.get('SERVER_NAME'))
    invalid_url = 'http://invalid.org'

    oauth_info = {
       'user_id': TEST_USER_ID,
       'next': client_url,
    }
    # validate session login redirect with invalid url
    oauth_info['next'] = invalid_url
    response4 = login(oauth_info=oauth_info)
    assert response4.status_code == 401


def test_redirect_validation_provider_login_valid_url(
        promote_user, login, test_client,
        eproms_app, client):
    promote_user(role_name=ROLE.ADMIN.value)
    promote_user(role_name=ROLE.STAFF.value)

    org = Organization(name='test org')
    user = get_user(TEST_USER_ID)
    with SessionScope(db):
        db.session.add(org)
        user.organizations.append(org)
        db.session.commit()

    test_client = db.session.merge(test_client)
    client_url = test_client._redirect_uris
    local_url = "http://{}/home?test".format(
        eproms_app.config.get('SERVER_NAME'))
    invalid_url = 'http://invalid.org'

    # validate provider login redirect with invalid url
    oauth_info = dict(OAUTH_INFO_PROVIDER_LOGIN)
    oauth_info['next'] = invalid_url
    response5 = login(oauth_info=oauth_info)
    assert response5.status_code == 401


def test_redirect_validation_challenge_post(
        promote_user, login, test_client,
        eproms_app, client):
    promote_user(role_name=ROLE.ADMIN.value)
    promote_user(role_name=ROLE.STAFF.value)

    org = Organization(name='test org')
    user = get_user(TEST_USER_ID)
    with SessionScope(db):
        db.session.add(org)
        user.organizations.append(org)
        db.session.commit()

    login()

    test_client = db.session.merge(test_client)
    client_url = test_client._redirect_uris
    local_url = "http://{}/home?test".format(
        eproms_app.config.get('SERVER_NAME'))
    invalid_url = 'http://invalid.org'

    # validate redirect of /challenge POST
    formdata = {'user_id': TEST_USER_ID, 'next_url': local_url}
    response6 = client.post('/challenge', data=formdata)
    assert response6.status_code == 200

    formdata['next_url'] = invalid_url
    response7 = client.post('/challenge', data=formdata)
    assert response7.status_code == 401
