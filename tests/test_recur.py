"""Module to test Recur model"""
from datetime import datetime, timedelta

from portal.models.recur import Recur
from tests import TestCase


class TestRecur(TestCase):

    def test_expired(self):
        back_36 = datetime.utcnow() - timedelta(days=36)
        recur = Recur(start='{"days": 30}', cycle_length='{"days": 2}',
                      termination='{"days": 35}')
        result = recur.active_interval_start(trigger_date=back_36)
        # None implies expired or not started
        self.assertIsNone(result)

    def test_not_started(self):
        yesterday = datetime.utcnow() - timedelta(days=1)
        recur = Recur(start='{"days": 2}', cycle_length='{"days": 2}',
                      termination='{"days": 35}')
        result = recur.active_interval_start(trigger_date=yesterday)
        # None implies expired or not started
        self.assertIsNone(result)

    def test_first_interval(self):
        three_back = datetime.utcnow() - timedelta(days=3)
        recur = Recur(start='{"days": 2}', cycle_length='{"days": 10}',
                      termination='{"days": 35}')
        result = recur.active_interval_start(trigger_date=three_back)
        # should get three back plus start
        self.assertAlmostEqual(result, three_back + timedelta(days=2))

    def test_third_interval(self):
        thirty_back = datetime.utcnow() - timedelta(days=30)
        recur = Recur(start='{"days": 2}', cycle_length='{"days": 10}',
                      termination='{"days": 35}')
        result = recur.active_interval_start(trigger_date=thirty_back)
        # should get back 30 back, plus 2 to start, plus 10*2
        self.assertAlmostEqual(result, thirty_back + timedelta(days=22))
