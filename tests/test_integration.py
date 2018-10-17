"""Unit test module for Selenium testing"""
from __future__ import unicode_literals  # isort:skip

import os
import sys
import unittest

from flask_testing import LiveServerTestCase
import pytest

if not pytest.config.getoption("--include-ui-testing"):
    pytest.skip(
        "--include-ui-testing is missing, skipping tests",
        allow_module_level=True,
    )

from selenium import webdriver  # noqa isort:skip
import xvfbwrapper  # noqa isort:skip

from .pages import LoginPage  # noqa isort:skip
from tests import TestCase  # noqa isort:skip


@unittest.skipUnless(
    (
        "SAUCE_USERNAME" in os.environ or
        xvfbwrapper.Xvfb().xvfb_exists()
    ),
    "Xvfb not installed"
)
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
            self.xvfb = xvfbwrapper.Xvfb()
            self.addCleanup(self.xvfb.stop)
            self.xvfb.start()

            self.driver = webdriver.Firefox(timeout=60)

        self.addCleanup(self.driver.quit)

        self.driver.root_uri = self.get_server_url()

        super(TestUI, self).setUp()

    def tearDown(self):
        """Clean db session, drop all tables."""

        # Update job result metadata on Sauce Labs, if available
        if (
            "SAUCE_USERNAME" in os.environ and
            "SAUCE_ACCESS_KEY" in os.environ and

            # No exception being handled - test completed successfully
            sys.exc_info() == (None, None, None)
        ):
            self.driver.execute_script("sauce:job-result=passed")

        super(TestUI, self).tearDown()

    def test_login_page(self):
        """Ensure login page loads successfully"""

        page = LoginPage(self.driver)
        page.get("/user/sign-in")

        assert "Uh-oh" not in page.w.find_element_by_tag_name("body").text

    def test_login_form_fb_exists(self):
        """Ensure Facebook button present on login form"""

        page = LoginPage(self.driver)
        page.get("/user/sign-in")

        assert page.facebook_button is not None
