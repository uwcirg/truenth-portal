from tests import TestCase, LAST_NAME, FIRST_NAME


class TestTrueNTH(TestCase):

    def test_portal_wrapper_html(self):
        self.login()
        rv = self.client.get('/api/portal-wrapper-html/')

        results = unicode(rv.data, 'utf-8')
        self.assertTrue(FIRST_NAME in results)
        self.assertTrue(LAST_NAME in results)

    def test_portal_wrapper_wo_name(self):
        "w/o a users first, last name, username should appear"
        username = 'test2@example.com'
        user = self.add_user(username=username, first_name=None)
        self.login(user_id=user.id)
        rv = self.client.get('/api/portal-wrapper-html/')

        self.assertEqual(rv.status_code, 200)
        self.assertTrue(username in rv.data)
