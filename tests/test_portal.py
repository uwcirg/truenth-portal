"""Unit test module for portal views"""
from tests import TestCase

from portal.models.user import User


class TestPortal(TestCase):
    """Portal view tests"""

    def test_admin_list(self):
        """Test admin view lists all users"""
        # Generate a few users with a splattering of roles
        u1 = self.add_user(username='u1')
        u2 = self.add_user(username='u2')
        self.promote_user(u1, role_name='admin')
        self.promote_user(u2, role_name='application_developer')

        # Test user needs admin role to view list
        self.promote_user(role_name='admin')
        self.login()
        rv = self.app.get('/admin')

        # Should at least see an entry per user in system
        self.assertEquals(rv.data.count('id="name"'), User.query.count())
