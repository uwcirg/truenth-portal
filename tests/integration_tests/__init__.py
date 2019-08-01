"""Unit test module for Selenium testing"""

import os
import sys
import unittest

from flask_testing import LiveServerTestCase
import pytest
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
import xvfbwrapper

from tests import TestCase


@unittest.skipUnless(
    (
        "SAUCE_USERNAME" in os.environ or
        xvfbwrapper.Xvfb().xvfb_exists()
    ),
    "Xvfb not installed"
)
class IntegrationTestCase(TestCase, LiveServerTestCase):
    """Test class for UI integration/workflow testing"""

    def setUp(self):
        """Reset all tables before testing."""

        if "SAUCE_USERNAME" in os.environ:
            # Configure driver for Sauce Labs
            # Presumes tunnel setup by Sauce Connect
            # On TravisCI, Sauce Connect tunnel setup by Sauce Labs addon
            # https://docs.travis-ci.com/user/sauce-connect
            platform = {
                "browserName": "firefox",
                "platform": "Windows 10",
                "version": "60.0",
            }
            capabilities = {
                "tunnel-identifier": os.environ["TRAVIS_JOB_NUMBER"],
                "extendedDebugging": "true",
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

            url = "http://{user}:{access_key}@localhost:4445/wd/hub".format(
                user=os.environ["SAUCE_USERNAME"],
                access_key=os.environ["SAUCE_ACCESS_KEY"],
            )

            self.driver = webdriver.Remote(
                desired_capabilities=capabilities,
                command_executor=url
            )

        else:
            if "DISPLAY" not in os.environ:
                # Non-graphical environment; use xvfb
                self.xvfb = xvfbwrapper.Xvfb()
                self.addCleanup(self.xvfb.stop)
                self.xvfb.start()
            self.driver = webdriver.Firefox(timeout=60)

        self.addCleanup(self.driver.quit)

        self.driver.root_uri = self.get_server_url()
        self.driver.implicitly_wait(30)
        self.verificationErrors = []
        # default explicit wait time; use with Expected Conditions as needed
        self.wait = WebDriverWait(self.driver, 60)
        self.accept_next_alert = True

        super(IntegrationTestCase, self).setUp()

    def is_element_present(self, how, what):
        """Detects whether or not an element can be found in DOM

        This function was exported from Selenium IDE
        """
        try:
            self.driver.find_element(by=how, value=what)
        except NoSuchElementException as e:
            return False
        return True

    def is_alert_present(self):
        """Detects whether an alert message is present

        This function was exported from Selenium IDE
        """
        try:
            self.driver.switch_to_alert()
        except NoAlertPresentException as e:
            return False
        return True

    def close_alert_and_get_its_text(self):
        """Closes an alert, if present, and returns its text

        If an alert is not present a NoAlertPresentException
        will be thrown.
        This function was exported from Selenium IDE
        """
        try:
            alert = self.driver.switch_to_alert()
            alert_text = alert.text
            if self.accept_next_alert:
                alert.accept()
            else:
                alert.dismiss()
            return alert_text
        finally:
            self.accept_next_alert = True

    def tearDown(self):
        """Clean db session, drop all tables."""

        # Update job result metadata on Sauce Labs, if available
        if (
            "SAUCE_USERNAME" in os.environ and

            # No exception being handled - test completed successfully
            sys.exc_info() == (None, None, None)
        ):
            self.driver.execute_script("sauce:job-result=passed")

        self.assertEqual([], self.verificationErrors)

        super(IntegrationTestCase, self).tearDown()
