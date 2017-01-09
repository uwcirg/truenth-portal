"""Test module for patient specific APIs"""
from tests import TestCase, TEST_USERNAME
from portal.models.role import ROLE


class TestPatient(TestCase):

    def test_email_search(self):
        self.promote_user(role_name=ROLE.PATIENT)
        self.login()
        rv = self.client.get(
            '/api/patient?email={}'.format(TEST_USERNAME),
            follow_redirects=True)
        # Known patient but w/o patient role should 404
        self.assert200(rv)
        self.assertTrue(rv.json['resourceType'] == 'Patient')

    def test_email_search_non_patient(self):
        self.login()
        rv = self.client.get(
            '/api/patient?email={}'.format(TEST_USERNAME),
            follow_redirects=True)
        # Known patient but w/o patient role should 404
        self.assert404(rv)

    def test_inadequate_perms(self):
        dummy = self.add_user(username='dummy@example.com')
        self.promote_user(user=dummy, role_name=ROLE.PATIENT)
        self.login()
        rv = self.client.get(
            '/api/patient?email={}'.format('dummy@example.com'),
            follow_redirects=True)
        # w/o permission, should see a 404 not a 401 on search
        self.assert404(rv)
