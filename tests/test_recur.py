"""Module to test Recur model"""
from datetime import datetime, timedelta

from portal.models.recur import Recur
from tests import TestCase


class TestRecur(TestCase):

    def test_expired(self):
        back_36 = datetime.utcnow() - timedelta(days=36)
        recur = Recur(days_to_start=30, days_in_cycle=2,
                      days_till_termination=35)
        result = recur.active_interval_start(start=back_36)
        # None implies expired or not started
        self.assertIsNone(result)

    def test_not_started(self):
        yesterday = datetime.utcnow() - timedelta(days=1)
        recur = Recur(days_to_start=2, days_in_cycle=2,
                      days_till_termination=35)
        result = recur.active_interval_start(start=yesterday)
        # None implies expired or not started
        self.assertIsNone(result)

    def test_first_interval(self):
        three_back = datetime.utcnow() - timedelta(days=3)
        recur = Recur(days_to_start=2, days_in_cycle=10,
                      days_till_termination=35)
        result = recur.active_interval_start(start=three_back)
        # should get three back plus days_to_start
        self.assertAlmostEqual(result, three_back + timedelta(days=2))

    def test_third_interval(self):
        thirty_back = datetime.utcnow() - timedelta(days=30)
        recur = Recur(days_to_start=2, days_in_cycle=10,
                      days_till_termination=35)
        result = recur.active_interval_start(start=thirty_back)
        # should get back 30 back, plus 2 to start, plus 10*2
        self.assertAlmostEqual(result, thirty_back + timedelta(days=22))
