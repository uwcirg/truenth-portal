"""Unit test module for terms of use logic"""
import json

from portal.extensions import db
from portal.extensions import celery
from portal.models.role import ROLE
from portal.models.scheduled_job import ScheduledJob
from portal.tasks import test, info
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

    def test_job_upsert(self):
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        data = {
                "name": "testjob",
                "task": "info",
                "schedule": "* * * * *",
               }
        resp = self.client.post(
            '/api/scheduled_jobs',
            content_type='application/json',
            data=json.dumps(data))
        self.assert200(resp)
        self.assertEquals(resp.json['schedule'], '* * * * *')

        data['schedule'] = "0 0 0 0 0"
        resp = self.client.post(
            '/api/scheduled_jobs',
            content_type='application/json',
            data=json.dumps(data))
        self.assert200(resp)
        self.assertEquals(resp.json['schedule'], '0 0 0 0 0')

    def test_job_get(self):
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        job = ScheduledJob(name="testjob", task="info", schedule="0 0 * * *")
        db.session.add(job)
        db.session.commit()
        job = db.session.merge(job)

        resp = self.client.get('/api/scheduled_jobs/{}'.format(job.id))
        self.assert200(resp)
        self.assertEquals(resp.json['task'], 'info')

        resp = self.client.get('/api/scheduled_jobs/999')
        self.assert400(resp)

    def test_job_delete(self):
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        job = ScheduledJob(name="testjob", task="info", schedule="0 0 * * *")
        db.session.add(job)
        db.session.commit()
        job = db.session.merge(job)

        resp = self.client.delete('/api/scheduled_jobs/{}'.format(job.id))
        self.assert200(resp)
        self.assertFalse(ScheduledJob.query.all())

        resp = self.client.delete('/api/scheduled_jobs/999')
        self.assert400(resp)
