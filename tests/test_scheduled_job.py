"""Unit test module for scheduled jobs logic"""
from flask_webtest import SessionScope
import json

from portal.extensions import db
from portal.models.role import ROLE
from portal.models.scheduled_job import ScheduledJob
from portal.tasks import test
from tests import TestCase



class TestScheduledJob(TestCase):
    """Scheduled Job tests"""

    def test_schedule(self):
        schedule = "45 * * * *"
        sj = ScheduledJob(name="test_sched", task="test",
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
                "name": "test_upsert",
                "task": "test",
                "schedule": "* * * * *",
               }
        resp = self.client.post(
            '/api/scheduled_job',
            content_type='application/json',
            data=json.dumps(data))
        self.assert200(resp)
        self.assertEquals(resp.json['schedule'], '* * * * *')

        data['schedule'] = "0 0 0 0 0"
        resp = self.client.post(
            '/api/scheduled_job',
            content_type='application/json',
            data=json.dumps(data))
        self.assert200(resp)
        self.assertEquals(resp.json['schedule'], '0 0 0 0 0')

    def test_job_get(self):
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        job = ScheduledJob(name="test_get", task="test", schedule="0 0 * * *")
        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
            job = db.session.merge(job)
            job_id = job.id

        resp = self.client.get('/api/scheduled_job/{}'.format(job_id))
        self.assert200(resp)
        self.assertEquals(resp.json['task'], 'test')

        resp = self.client.get('/api/scheduled_job/999')
        self.assert404(resp)

    def test_job_delete(self):
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        job = ScheduledJob(name="test_del", task="test", schedule="0 0 * * *")
        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
            job = db.session.merge(job)
            job_id = job.id

        resp = self.client.delete('/api/scheduled_job/{}'.format(job_id))
        self.assert200(resp)
        self.assertFalse(ScheduledJob.query.all())

        resp = self.client.delete('/api/scheduled_job/999')
        self.assert404(resp)

    def test_job_trigger(self):
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        job = ScheduledJob(name="test_trig", task="test", schedule="0 0 * * *")
        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
            job = db.session.merge(job)
            job_id = job.id

        resp = self.client.post('/api/scheduled_job/{}/trigger'.format(job_id))
        self.assert200(resp)
        self.assertEquals(resp.json['message'], 'Test task complete.')
