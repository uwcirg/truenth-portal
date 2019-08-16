"""Unit test module for portal views"""

from tests import TestCase


class TestCelery(TestCase):
    """Portal view tests"""

    def test_celery_add(self):
        """Try simply add task handed off to celery"""
        x = 151
        y = 99
        response = (self.client.get(
            '/celery-test?x={x}&y={y}'.format(x=x, y=y)))
        assert response.status_code == 200
        assert response.json['result'] == x + y
