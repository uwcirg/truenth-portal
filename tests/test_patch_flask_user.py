"""Unit test module for patch_flask_user"""
from flask import current_app

from portal.views.patch_flask_user import patch_make_safe_url
from tests import TestCase


class TestPathFlaskUser(TestCase):

    def test_no_path(self):
        url = 'http://google.com'
        safe_url = patch_make_safe_url(url)
        assert '' == safe_url

    def test_no_qs(self):
        url = 'https://google.com/'
        safe_url = patch_make_safe_url(url)
        assert '/' == safe_url

    def test_w_qs(self):
        url = 'https://google.com/search?q=testing'
        safe_url = patch_make_safe_url(url)
        assert '/search?q=testing' == safe_url

    def test_wo_host_scheme(self):
        url = '/search?q=testing&safe=on'
        safe_url = patch_make_safe_url(url)
        assert '/search?q=testing&safe=on' == safe_url

    def test_fragment_wo_host(self):
        url = '/search?q=testing&safe=on#row=4'
        safe_url = patch_make_safe_url(url)
        assert url == safe_url

    def test_qs_and_fragment(self):
        url = 'https://google.com:443/search?q=testing&safe=on#row=4'
        safe_url = patch_make_safe_url(url)
        index = url.find('/search')
        assert url[index:] == safe_url

    def test_user_manager_find_user_wildcards_not_respected(self):
        # At the time of writing this test flask-user looked up
        # users using the LIKE clause which treats certain characters
        # as special character, such as '_' which is treated as a wild card.
        # This test will help us ensure that we avoid special characters
        # when looking up users
        self.add_user(username='foo', email='someUsername@example.com')
        user_manager = current_app.user_manager
        user = user_manager.find_user_by_email('some_sername@example.com')[0]
        assert user is None

    def test_user_manager_find_user_case_insensitive(self):
        added_user = self.add_user(
            username='foo',
            email='CrAzYcAsInG@example.com'
        )
        user_manager = current_app.user_manager
        user = user_manager.find_user_by_email('crazycasing@example.com')[0]
        assert user is not None
        assert user.id == added_user.id
