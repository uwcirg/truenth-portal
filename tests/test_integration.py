"""Unit test module for Selenium testing"""
import os
from selenium import webdriver

from flask.ext.testing import LiveServerTestCase

from tests import TestCase
from pages import LoginPage


class TestUI(TestCase, LiveServerTestCase):
    """Test class for UI integration/workflow testing"""

    def setUp(self):
        """Reset all tables before testing."""

        if "SAUCE_USERNAME" in os.environ and "SAUCE_ACCESS_KEY" in os.environ:

            platform = {
                "browserName": "firefox",
                "platform": "Windows 10",
                "version": "46.0",
            }
            capabilities = {
                "tunnel-identifier": os.environ["TRAVIS_JOB_NUMBER"],
            }
            metadata = {
                "name": self.id(),
                "build": "#%s %s" % (
                    os.environ["TRAVIS_BUILD_NUMBER"],
                    os.environ["TRAVIS_BRANCH"],
                ),
                "tags": [
                    "py" + os.environ["TRAVIS_PYTHON_VERSION"],
                    "CI",
                ],
                "passed": False,
            }
            capabilities.update(platform)
            capabilities.update(metadata)

            url = "http://{username}:{access_key}@localhost:4445/wd/hub".format(
                username=os.environ["SAUCE_USERNAME"],
                access_key=os.environ["SAUCE_ACCESS_KEY"],
            )

            self.driver = webdriver.Remote(
                desired_capabilities=capabilities,
                command_executor=url
            )

        else:
            self.driver = webdriver.Firefox()

        self.addCleanup(self.driver.quit)

        self.driver.implicitly_wait(60)
        self.driver.root_uri = self.get_server_url()

        super(TestUI, self).setUp()

    def tearDown(self):
        """Clean db session, drop all tables."""

        # Update job result metadata on Sauce Labs, if available
        if (
            not self._resultForDoCleanups.failures and
            not self._resultForDoCleanups.errors and
            "SAUCE_USERNAME" in os.environ and
            "SAUCE_ACCESS_KEY" in os.environ
        ):
            self.driver.execute_script("sauce:job-result=passed")

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
