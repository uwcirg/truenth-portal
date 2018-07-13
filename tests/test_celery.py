"""Unit test module for portal views"""
import sys

import pytest

from tests import TestCase

if sys.version_info.major > 2:
    pytest.skip(msg="not yet ported to python3", allow_module_level=True)
class TestCelery(TestCase):
    """Portal view tests"""

    def test_celery_add(self):
        """Try simply add task handed off to celery"""
        x = 151
        y = 99
        rv = self.client.get('/celery-test?x={x}&y={y}&redirect-to-result=True'. \
                             format(x=x, y=y), follow_redirects=True)
        self.assert200(rv)
        self.assertEqual(rv.data, str(x + y))
