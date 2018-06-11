"""Unit test module for patch_flask_user"""
from portal.views.patch_flask_user import patch_make_safe_url
from tests import TestCase


class TestPathFlaskUser(TestCase):

    def test_no_path(self):
        url = u'http://google.com'
        safe_url = patch_make_safe_url(url)
        self.assertEqual('', safe_url)

    def test_no_qs(self):
        url = u'https://google.com/'
        safe_url = patch_make_safe_url(url)
        self.assertEqual('/', safe_url)

    def test_w_qs(self):
        url = u'https://google.com/search?q=testing'
        safe_url = patch_make_safe_url(url)
        self.assertEqual('/search?q=testing', safe_url)

    def test_wo_host_scheme(self):
        url = u'/search?q=testing&safe=on'
        safe_url = patch_make_safe_url(url)
        self.assertEqual('/search?q=testing&safe=on', safe_url)

    def test_fragment_wo_host(self):
        url = u'/search?q=testing&safe=on#row=4'
        safe_url = patch_make_safe_url(url)
        self.assertEqual(url, safe_url)

    def test_qs_and_fragment(self):
        url = u'https://google.com:443/search?q=testing&safe=on#row=4'
        safe_url = patch_make_safe_url(url)
        index = url.find('/search')
        self.assertEqual(url[index:], safe_url)
