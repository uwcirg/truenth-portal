"""Unit test module for portal views"""

from datetime import datetime
import tempfile
import urllib

from flask_swagger import swagger
from flask_webtest import SessionScope
from swagger_spec_validator import validate_spec_url

from portal.config.config import TestConfig
from portal.extensions import db
from portal.factories.app import create_app
from portal.models.intervention import INTERVENTION, UserIntervention
from portal.models.message import EmailMessage
from portal.models.organization import Organization
from portal.models.role import ROLE
from portal.models.user import User
from portal.system_uri import ICHOM
from tests import OAUTH_INFO_PROVIDER_LOGIN, TEST_USER_ID, TestCase


class TestPortal(TestCase):
    """Portal view tests"""

    def test_card_html(self):
        """Interventions can customize the button text """
        client = self.add_client()
        intervention = INTERVENTION.DECISION_SUPPORT_P3P
        intervention.public_access = True  # make the card avail for the test
        client.intervention = intervention
        intervention.card_html = "Custom Label"

        self.add_required_clinical_data()
        self.bless_with_basics(setdate=datetime.utcnow())
        self.add_procedure(code='1', display='Watchful waiting', system=ICHOM)
        self.login()
        response = self.client.get('/home')
        assert response.status_code == 200

        assert 'Custom Label' in response.get_data(as_text=True)
        intervention = db.session.merge(intervention)
        assert intervention.card_html in response.get_data(as_text=True)

    def test_user_card_html(self):
        """Interventions can further customize per user"""
        client = self.add_client()
        intervention = INTERVENTION.DECISION_SUPPORT_P3P
        intervention.public_access = True  # make the card avail for the test
        client.intervention = intervention
        ui = UserIntervention(
            user_id=TEST_USER_ID, intervention_id=intervention.id)
        ui.card_html = "<b>Bold Card Text</b>"
        ui.link_label = "Custom User Label"
        ui.link_url = 'http://example.com/?test=param1'
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()

        self.add_required_clinical_data()
        self.bless_with_basics(setdate=datetime.utcnow())
        self.add_procedure(code='1', display='Watchful waiting', system=ICHOM)
        self.login()
        user = db.session.merge(self.test_user)

        response = self.client.get('/home')
        assert response.status_code == 200

        ui = db.session.merge(ui)
        assert ui.card_html in response.get_data(as_text=True)
        assert ui.link_label in response.get_data(as_text=True)
        assert ui.link_url in response.get_data(as_text=True)
        intervention = db.session.merge(intervention)
        assert (
            intervention.display_for_user(user).link_label
            in response.get_data(as_text=True))

    def test_public_access(self):
        """Interventions w/o public access should be hidden"""
        client = self.add_client()
        intervention = INTERVENTION.sexual_recovery
        client.intervention = intervention
        intervention.public_access = False

        self.login()
        self.add_required_clinical_data()
        self.bless_with_basics()
        response = self.client.get('/home')

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
        response = self.client.get('/home')

        assert 'Sexual Recovery' in response.get_data(as_text=True)

    def test_admin_list(self):
        """Test admin view lists all users"""
        # Generate a few users with a smattering of roles
        u1 = self.add_user(username='u1@foo.bar')
        u2 = self.add_user(username='u2@bar.foo')
        self.promote_user(u1, role_name=ROLE.ADMIN.value)
        self.promote_user(u2, role_name=ROLE.APPLICATION_DEVELOPER.value)

        # Test user needs admin role to view list
        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()
        response = self.client.get('/admin')

        # Should at least see an entry per user in system
        assert (response.get_data(as_text=True).count('/profile')
                >= User.query.count())

    def test_invite(self):
        """Test email invite form"""
        test_user = User.query.get(TEST_USER_ID)
        test_user.email = 'test_user@uw.edu'
        db.session.add(test_user)
        db.session.commit()

        self.login()
        postdata = {
            'subject': 'unittest subject',
            'recipients': 'test_user@yahoo.com test_user@uw.edu',
            'body': "Ode to joy"}
        response = self.client.post('/invite', data=postdata,
                                    follow_redirects=True)
        assert "Email Invite Sent" in response.get_data(as_text=True)

    def test_message_sent(self):
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

        self.login()
        response = self.client.get('/invite/{0}'.format(message.id))
        assert (response.get_data(as_text=True).find(
            sent_at.strftime('%m/%d/%Y %H:%M:%S')) > 0)
        assert (response.get_data(as_text=True).find('one@ex1.com two@two.org')
                > 0)

    def test_missing_message(self):
        """Request to view non existant message should 404"""
        self.login()
        response = self.client.get('/invite/404')
        assert response.status_code == 404

    def test_swagger_docgen(self):
        """Build swagger docs for entire project"""

        expected_keys = (
            'info',
            'paths',
            'swagger',
            'definitions',
        )
        swag = swagger(self.client.application)

        for key in expected_keys:
            assert key in swag

    def test_swagger_validation(self):
        """Ensure our swagger spec matches swagger schema"""

        with tempfile.NamedTemporaryFile(
            prefix='swagger_test_',
            suffix='.json',
            delete=True,
        ) as temp_spec:
            temp_spec.write(self.client.get('/spec').data)
            temp_spec.seek(0)

            validate_spec_url("file:%s" % temp_spec.name)

    def test_report_error(self):
        self.login()
        params = {
            'subject_id': 112,
            'page_url': '/not/real',
            'message': 'creative test string'
        }
        response = self.client.get('/report-error?{}'.format(
            urllib.parse.urlencode(params)))
        assert response.status_code == 200

    def test_configuration_settings(self):
        self.login()
        lr_group = self.app.config['LR_GROUP']
        response = self.client.get('/api/settings/lr_group')
        assert response.status_code == 200
        assert response.json.get('LR_GROUP') == lr_group
        response2 = self.client.get('/api/settings/bad_value')
        assert response2.status_code == 400

    def test_configuration_secrets(self):
        """Ensure config keys containing secrets are not exposed"""
        blacklist = (
            'SECRET',
            'URI',
            'SQL',
        )
        response = self.client.get('/api/settings')

        assert response.status_code == 200
        assert not any(
            any(k in config_key for k in blacklist)
            for config_key in response.json
        )


class TestPortalEproms(TestCase):
    """Portal views depending on eproms blueprint"""

    def create_app(self):
        """
        Overload base version to hide the GIL (allows registration of ePROMs)
        """
        tc = TestConfig()
        setattr(tc, 'HIDE_GIL', True)
        self._app = create_app(tc)
        return self._app

    def test_redirect_validation(self):
        self.promote_user(role_name=ROLE.ADMIN.value)
        self.promote_user(role_name=ROLE.STAFF.value)

        org = Organization(name='test org')
        user = User.query.get(TEST_USER_ID)
        with SessionScope(db):
            db.session.add(org)
            user.organizations.append(org)
            db.session.commit()

        self.login()

        client = self.add_client()
        client_url = client._redirect_uris
        local_url = "http://{}/home?test".format(
            self.app.config.get('SERVER_NAME'))
        invalid_url = 'http://invalid.org'

        # validate redirect of /website-consent-script GET
        response = self.client.get(
            '/website-consent-script/{}'.format(TEST_USER_ID),
            query_string={'redirect_url': local_url}
        )
        assert response.status_code == 200

        response2 = self.client.get(
            '/website-consent-script/{}'.format(TEST_USER_ID),
            query_string={'redirect_url': invalid_url}
        )
        assert response2.status_code == 401

        # validate session login redirect with valid url
        oauth_info = {
            'user_id': TEST_USER_ID,
            'next': client_url,
        }
        response3 = self.login(oauth_info=oauth_info)
        assert response3.status_code == 200

        # validate session login redirect with invalid url
        oauth_info['next'] = invalid_url
        response4 = self.login(oauth_info=oauth_info)
        assert response4.status_code == 401

        # validate provider login redirect with invalid url
        oauth_info = dict(OAUTH_INFO_PROVIDER_LOGIN)
        oauth_info['next'] = invalid_url
        response5 = self.login(oauth_info=oauth_info)
        assert response5.status_code == 401

        # validate redirect of /challenge POST
        formdata = {'user_id': TEST_USER_ID, 'next_url': local_url}
        response6 = self.client.post('/challenge', data=formdata)
        assert response6.status_code == 200

        formdata['next_url'] = invalid_url
        response7 = self.client.post('/challenge', data=formdata)
        assert response7.status_code == 401
