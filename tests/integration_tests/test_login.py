from flask import url_for

from tests import DEFAULT_PASSWORD, TEST_USERNAME
from tests.integration_tests import IntegrationTestCase


class TestLogin(IntegrationTestCase):
    """Test class for Login integration tests"""

    def test_login_page(self):
        """Ensure login works properly"""
        driver = self.driver
        driver.get(url_for("user.login", _external=True))

        driver.find_element_by_name("email").click()
        driver.find_element_by_name("email").clear()
        driver.find_element_by_name("email").send_keys(TEST_USERNAME)
        driver.find_element_by_name("password").click()
        driver.find_element_by_name("password").clear()
        driver.find_element_by_name("password").send_keys(DEFAULT_PASSWORD)
        driver.find_element_by_xpath(
            "//input[@class='btn btn-tnth-primary btn-lg' and @value='LOG IN']").click()
        driver.find_element_by_id("tnthUserBtn").click()
        driver.find_element_by_link_text("Log Out of TrueNTH").click()
