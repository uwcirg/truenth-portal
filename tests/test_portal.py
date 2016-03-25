"""Unit test module for portal views"""

from datetime import datetime
from flask.ext.webtest import SessionScope
from flask_swagger import swagger
from swagger_spec_validator import validate_spec_url
import tempfile

from portal.extensions import db
from portal.models.intervention import Intervention, INTERVENTION
from portal.models.intervention import UserIntervention
from portal.models.role import ROLE
from portal.models.user import User
from portal.models.message import EmailInvite
from tests import TestCase, TEST_USER_ID


class TestPortal(TestCase):
    """Portal view tests"""

    def test_card_html(self):
        """Interventions can customize the button text """
        client = self.add_test_client()
        intervention = Intervention.query.filter_by(
            name=INTERVENTION.SEXUAL_RECOVERY).first()
        client.intervention = intervention
        intervention.card_html = "Custom Label"

        self.add_required_clinical_data()
        self.login()
        rv = self.app.get('/home')

        self.assertIn('Decision Support', rv.data)
        self.assertIn(intervention.card_html, rv.data)

    def test_public_access(self):
        """Interventions w/o public access should be hidden"""
        client = self.add_test_client()
        intervention = Intervention.query.filter_by(
            name=INTERVENTION.DECISION_SUPPORT_P3P).first()
        client.intervention = intervention
        intervention.public_access = False

        self.add_required_clinical_data()
        self.login()
        rv = self.app.get('/home')

        self.assertNotIn('Decision Support', rv.data)

        # now give just the test user access
        ui = UserIntervention(user_id=TEST_USER_ID,
                              intervention_id=intervention.id,
                              access="granted")
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()
        rv = self.app.get('/home')

        self.assertIn('Decision Support', rv.data)

    def test_admin_list(self):
        """Test admin view lists all users"""
        # Generate a few users with a smattering of roles
        u1 = self.add_user(username='u1')
        u2 = self.add_user(username='u2')
        self.promote_user(u1, role_name=ROLE.ADMIN)
        self.promote_user(u2, role_name=ROLE.APPLICATION_DEVELOPER)

        # Test user needs admin role to view list
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.app.get('/admin')

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
        rv = self.app.post('/invite', data=postdata, follow_redirects=True)
        self.assertTrue("Email Invite Sent" in rv.data)

    def test_message_sent(self):
        """Email invites - test view for sent messages"""
        sent_at = datetime.strptime("2000/01/01 12:31:00",
                "%Y/%m/%d %H:%M:%S")
        message = EmailInvite(subject='a subject', user_id=TEST_USER_ID,
                sender="testuser@email.com",
                body='Welcome to testing', sent_at=sent_at,
                recipients="one@ex1.com two@two.org")
        db.session.add(message)
        db.session.commit()

        self.login()
        rv = self.app.get('/invite/{0}'.format(message.id))
        self.assertTrue(rv.data.find(sent_at.strftime('%m/%d/%Y %H:%M:%S'))
            > 0)
        self.assertTrue(rv.data.find('one@ex1.com two@two.org') > 0)

    def test_missing_message(self):
        """Request to view non existant message should 404"""
        self.login()
        rv = self.app.get('/invite/404')
        self.assertEquals(rv.status_code, 404)

    def test_celery_add(self):
        """Try simply add task handed off to celery"""
        x = 151
        y = 99
        rv = self.app.get('/celery-test?x={x}&y={y}&redirect-to-result=True'.\
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
        swag = swagger(self.app.application)

        for key in expected_keys:
            self.assertIn(key, swag)

    def test_swagger_validation(self):
        """Ensure our swagger spec matches swagger schema"""

        with tempfile.NamedTemporaryFile(
            prefix='swagger_test_',
            suffix='.json',
            delete=True,
        ) as temp_spec:
            temp_spec.write(self.app.get('/spec').data)
            temp_spec.seek(0)

            validate_spec_url("file:%s" % temp_spec.name)
