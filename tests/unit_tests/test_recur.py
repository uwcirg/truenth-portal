"""Module to test Recur model"""
from __future__ import unicode_literals  # isort:skip

from datetime import datetime, timedelta

import pytest

from portal.models.recur import Recur
from tests import TestCase

now = datetime.utcnow()


class TestRecur(TestCase):

    def test_expired(self):
        back_36 = datetime.utcnow() - timedelta(days=36)
        recur = Recur(start='{"days": 30}', cycle_length='{"days": 2}',
                      termination='{"days": 35}')
        result, _ = recur.active_interval_start(
            trigger_date=back_36, as_of_date=now)
        # None implies expired or not started
        assert result is None

    def test_not_started(self):
        yesterday = datetime.utcnow() - timedelta(days=1)
        recur = Recur(start='{"days": 2}', cycle_length='{"days": 2}',
                      termination='{"days": 35}')
        result, _ = recur.active_interval_start(
            trigger_date=yesterday, as_of_date=now)
        # None implies expired or not started
        assert result is None

    def test_first_interval(self):
        three_back = datetime.utcnow() - timedelta(days=3)
        recur = Recur(start='{"days": 2}', cycle_length='{"days": 10}',
                      termination='{"days": 35}')
        result, ic = recur.active_interval_start(
            trigger_date=three_back, as_of_date=now)
        # should get three back plus start
        assert result == three_back + timedelta(days=2)
        assert ic == 0

    def test_third_interval(self):
        thirty_back = datetime.utcnow() - timedelta(days=30)
        recur = Recur(start='{"days": 2}', cycle_length='{"days": 10}',
                      termination='{"days": 35}')
        result, ic = recur.active_interval_start(
            trigger_date=thirty_back, as_of_date=now)
        # should get back 30 back, plus 2 to start, plus 10*2 (iterations)
        assert result == thirty_back + timedelta(days=22)
        assert ic == 2
