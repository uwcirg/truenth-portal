"""Unit test module for portal views"""

from datetime import datetime
from flask_webtest import SessionScope
from flask_swagger import swagger
from swagger_spec_validator import validate_spec_url
import tempfile
import urllib

from portal.extensions import db
from portal.models.intervention import INTERVENTION, UserIntervention
from portal.models.role import ROLE
from portal.models.user import User
from portal.models.message import EmailMessage
from tests import TestCase, TEST_USER_ID


class TestPortal(TestCase):
    """Portal view tests"""

    def test_card_html(self):
        """Interventions can customize the button text """
        client = self.add_client()
        intervention = INTERVENTION.DECISION_SUPPORT_P3P
        intervention.public_access = True  # make the card avail for the test
        client.intervention = intervention
        intervention.card_html = "Custom Label"

        self.login()
        self.add_required_clinical_data()
        self.bless_with_basics()
        rv = self.client.get('/home')
        self.assert200(rv)

        self.assertIn('Custom Label', rv.data)
        intervention = db.session.merge(intervention)
        self.assertIn(intervention.card_html, rv.data.decode('utf-8'))

    def test_user_card_html(self):
        """Interventions can further customize per user"""
        client = self.add_client()
        intervention = INTERVENTION.DECISION_SUPPORT_P3P
        intervention.public_access = True  # make the card avail for the test
        client.intervention = intervention
        ui = UserIntervention(user_id=TEST_USER_ID,
                              intervention_id=intervention.id)
        ui.card_html = "<b>Bold Card Text</b>"
        ui.link_label = "Custom User Label"
        ui.link_url = 'http://example.com/?test=param1'
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()

        self.login()
        self.add_required_clinical_data()
        self.bless_with_basics()
        user = db.session.merge(self.test_user)

        rv = self.client.get('/home')
        self.assert200(rv)

        ui = db.session.merge(ui)
        self.assertIn(ui.card_html, rv.data.decode('utf-8'))
        self.assertIn(ui.link_label, rv.data.decode('utf-8'))
        self.assertIn(ui.link_url, rv.data.decode('utf-8'))
        intervention = db.session.merge(intervention)
        self.assertIn(intervention.display_for_user(user).link_label, rv.data.decode('utf-8'))

    def test_staff_html(self):
        """Interventions can customize the staff text """
        client = self.add_client()
        intervention = INTERVENTION.sexual_recovery
        client.intervention = intervention
        ui = UserIntervention(user_id=TEST_USER_ID,
                              intervention_id=intervention.id)
        ui.staff_html = "Custom text for <i>staff</i>"
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()

        self.bless_with_basics()
        self.login()
        self.promote_user(role_name=ROLE.STAFF)
        self.promote_user(role_name=ROLE.PATIENT)

        # This test requires PATIENT_LIST_ADDL_FIELDS includes the
        # 'reports' field
        self.app.config['PATIENT_LIST_ADDL_FIELDS'] = [
            'reports',]
        rv = self.client.get('/patients/')

        ui = db.session.merge(ui)
        self.assertIn(ui.staff_html, rv.data)

    def test_public_access(self):
        """Interventions w/o public access should be hidden"""
        client = self.add_client()
        intervention = INTERVENTION.sexual_recovery
        client.intervention = intervention
        intervention.public_access = False

        self.login()
        self.add_required_clinical_data()
        self.bless_with_basics()
        rv = self.client.get('/home')

        self.assertNotIn('Sexual Recovery', rv.data)

        # now give just the test user access
        intervention = db.session.merge(intervention)
        ui = UserIntervention(user_id=TEST_USER_ID,
                              intervention_id=intervention.id,
                              access="granted")
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()
        rv = self.client.get('/home')

        self.assertIn('Sexual Recovery', rv.data)

    def test_admin_list(self):
        """Test admin view lists all users"""
        # Generate a few users with a smattering of roles
        u1 = self.add_user(username='u1@foo.bar')
        u2 = self.add_user(username='u2@bar.foo')
        self.promote_user(u1, role_name=ROLE.ADMIN)
        self.promote_user(u2, role_name=ROLE.APPLICATION_DEVELOPER)

        # Test user needs admin role to view list
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.client.get('/admin')

        # Should at least see an entry per user in system
        self.assertTrue(rv.data.count('/profile') >= User.query.count())

    def test_invite(self):
        """Test email invite form"""
        test_user = User.query.get(TEST_USER_ID)
        test_user.email = 'test_user@uw.edu'
        db.session.add(test_user)
        db.session.commit()

        self.login()
        postdata = { 'subject': 'unittest subject',
                'recipients': 'test_user@yahoo.com test_user@uw.edu',
                'body': "Ode to joy" }
        rv = self.client.post('/invite', data=postdata, follow_redirects=True)
        self.assertTrue("Email Invite Sent" in rv.data)

    def test_message_sent(self):
        """Email invites - test view for sent messages"""
        sent_at = datetime.strptime("2000/01/01 12:31:00",
                "%Y/%m/%d %H:%M:%S")
        message = EmailMessage(subject='a subject', user_id=TEST_USER_ID,
                sender="testuser@email.com",
                body='Welcome to testing', sent_at=sent_at,
                recipients="one@ex1.com two@two.org")
        db.session.add(message)
        db.session.commit()

        self.login()
        rv = self.client.get('/invite/{0}'.format(message.id))
        self.assertTrue(rv.data.find(sent_at.strftime('%m/%d/%Y %H:%M:%S'))
            > 0)
        self.assertTrue(rv.data.find('one@ex1.com two@two.org') > 0)

    def test_missing_message(self):
        """Request to view non existant message should 404"""
        self.login()
        rv = self.client.get('/invite/404')
        self.assertEquals(rv.status_code, 404)

    def test_celery_add(self):
        """Try simply add task handed off to celery"""
        x = 151
        y = 99
        rv = self.client.get('/celery-test?x={x}&y={y}&redirect-to-result=True'.\
                          format(x=x, y=y), follow_redirects=True)
        self.assert200(rv)
        self.assertEquals(rv.data, str(x + y))

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
            self.assertIn(key, swag)

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
        rv = self.client.get('/report-error?{}'.format(
            urllib.urlencode(params)))
        self.assert200(rv)

    def test_configuration_settings(self):
        self.login()
        lr_group = self.app.config['LR_GROUP']
        rv = self.client.get('/settings/lr_group')
        self.assert200(rv)
        self.assertEquals(rv.json.get('LR_GROUP'), lr_group)
        rv2 = self.client.get('/settings/bad_value')
        self.assertEquals(rv2.status_code, 400)
