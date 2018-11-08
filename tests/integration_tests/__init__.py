"""Unit test module for Selenium testing"""
from __future__ import unicode_literals  # isort:skip

import os
import sys
import unittest

from flask_testing import LiveServerTestCase
import pytest
from selenium import webdriver  # noqa isort:skip
import xvfbwrapper  # noqa isort:skip

from tests import TestCase  # noqa isort:skip


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

            url = "http://{user}:{access_key}@localhost:4445/wd/hub".format(
                user=os.environ["SAUCE_USERNAME"],
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

        super(IntegrationTestCase, self).setUp()

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

        super(IntegrationTestCase, self).tearDown()
