"""Unit test module for Selenium testing"""
from selenium import webdriver

from flask.ext.testing import LiveServerTestCase

from tests import TestCase
from pages import LoginPage


class TestUI(TestCase, LiveServerTestCase):
    """Test class for UI integration/workflow testing"""

    def setUp(self):
        """Reset all tables before testing."""

        super(TestUI, self).setUp()

        self.driver = webdriver.Firefox()
        self.driver.implicitly_wait(60)
        self.driver.root_uri = self.get_server_url()

    def tearDown(self):
        """Clean db session, drop all tables."""

        self.driver.quit()

        super(TestUI, self).tearDown()

    def test_login_page(self):
        """Ensure login page loads successfully"""

        page = LoginPage(self.driver)
        page.get("/user/sign-in")

        self.assertNotIn("Uh-oh", page.w.find_element_by_tag_name("body").text)

    def test_login_form_facebook_exists(self):
        """Ensure Facebook button present on login form"""

        page = LoginPage(self.driver)
        page.get("/user/sign-in")

        self.assertIsNotNone(page.facebook_button)
