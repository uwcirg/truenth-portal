"""Unit test module for terms of use logic"""
from datetime import datetime
from flask_webtest import SessionScope

from portal.extensions import db
from portal.extensions import celery
from portal.models.scheduled_job import ScheduledJob
from portal.tasks import test
from tests import TestCase, TEST_USER_ID

assert celery


class TestScheduledJob(TestCase):
    """Terms Of Use tests"""

    def test_schedule(self):
        schedule = "45 * * * *"
        sj = ScheduledJob(name="test", task="info",
                          schedule=schedule, active=True)
        sjc = sj.crontab_schedule()
        self.assertTrue(45 in sjc.minute)
        self.assertEquals(len(sjc.hour), 24)

        invalid_schedule = "monday to friday"
        with self.assertRaises(Exception):
            sj.schedule = invalid_schedule
        invalid_schedule = "* * * * * *"
        with self.assertRaises(Exception):
            sj.schedule = invalid_schedule
