"""Unit test module for portal views"""
from __future__ import unicode_literals  # isort:skip

from tests import TestCase


class TestCelery(TestCase):
    """Portal view tests"""

    def test_celery_add(self):
        """Try simply add task handed off to celery"""
        x = 151
        y = 99
        response = (self.client.get(
            '/celery-test?x={x}&y={y}&redirect-to-result=True'.
            format(x=x, y=y), follow_redirects=True))
        assert response.status_code == 200
        assert response.get_data(as_text=True) == str(x + y)
