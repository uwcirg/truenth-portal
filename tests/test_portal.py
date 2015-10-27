"""Unit test module for portal views"""
from datetime import datetime
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.role import ROLE
from portal.models.user import User
from portal.models.message import EmailInvite


class TestPortal(TestCase):
    """Portal view tests"""

    def test_admin_list(self):
        """Test admin view lists all users"""
        # Generate a few users with a splattering of roles
        u1 = self.add_user(username='u1')
        u2 = self.add_user(username='u2')
        self.promote_user(u1, role_name=ROLE.ADMIN)
        self.promote_user(u2, role_name=ROLE.APPLICATION_DEVELOPER)

        # Test user needs admin role to view list
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.app.get('/admin')

        # Should at least see an entry per user in system
        self.assertEquals(rv.data.count('id="name"'), User.query.count())

    def test_invite(self):
        """Test email invite form"""
        test_user = User.query.get(TEST_USER_ID)
        test_user.email = 'pbugni@uw.edu'
        db.session.add(test_user)
        db.session.commit()

        self.login()
        postdata = { 'subject': 'unittest subject',
                'recipients': 'bugni@yahoo.com pbugni@uw.edu',
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
