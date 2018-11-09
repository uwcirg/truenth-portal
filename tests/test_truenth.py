from __future__ import unicode_literals  # isort:skip

from tests import FIRST_NAME, LAST_NAME, TestCase


class TestTrueNTH(TestCase):

    def test_portal_wrapper_html(self):
        self.login()
        response = self.client.get('/api/portal-wrapper-html/')

        results = response.get_data(as_text=True)
        assert FIRST_NAME in results
        assert LAST_NAME in results

    def test_portal_wrapper_wo_name(self):
        "w/o a users first, last name, username should appear"
        username = 'test2@example.com'
        user = self.add_user(username=username, first_name=None)
        self.login(user_id=user.id)
        response = self.client.get('/api/portal-wrapper-html/')

        assert response.status_code == 200
        assert username in response.get_data(as_text=True)
