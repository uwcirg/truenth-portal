from .pages import LoginPage
from tests.integration_tests import IntegrationTestCase  # noqa isort:skip


class TestLogin(IntegrationTestCase):
    """Test class for Login integration tests"""

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
