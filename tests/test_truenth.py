from tests import TestCase, LAST_NAME, FIRST_NAME


class TestTrueNTH(TestCase):

    def test_portal_wrapper_html(self):
        self.login()
        rv = self.app.get('/api/portal-wrapper-html/')

        self.assertTrue(FIRST_NAME in rv.data)
        self.assertTrue(LAST_NAME in rv.data)

    def test_portal_wrapper_wo_name(self):
        "w/o a users first, last name, username should appear"
        username = 'test2'
        user = self.add_user(username=username, first_name=None)
        self.login(user_id=user.id)
        rv = self.app.get('/api/portal-wrapper-html/')

        self.assertEquals(rv.status_code, 200)
        self.assertTrue(username in rv.data)
