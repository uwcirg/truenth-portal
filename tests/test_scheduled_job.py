"""Unit test module for scheduled jobs logic"""
from flask_webtest import SessionScope
import json

from portal.extensions import db
from portal.models.role import ROLE
from portal.models.scheduled_job import ScheduledJob
from portal.tasks import test as test_task
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

        # test new job POST
        data = {"name": "test_upsert",
                "task": "test",
                "schedule": "* * * * *"}
        resp = self.client.post(
            '/api/scheduled_job',
            content_type='application/json',
            data=json.dumps(data))
        self.assert200(resp)
        job_id = resp.json['id']
        self.assertEquals(resp.json['schedule'], '* * * * *')

        # POST of an existing should raise a 400
        resp = self.client.post(
            '/api/scheduled_job',
            content_type='application/json',
            data=json.dumps(data))
        self.assert400(resp)

        # test existing job PUT
        data2 = {'schedule': "0 0 0 0 0"}
        resp = self.client.put(
            '/api/scheduled_job/{}'.format(job_id),
            content_type='application/json',
            data=json.dumps(data2))
        self.assert200(resp)
        self.assertEquals(resp.json['name'], data['name'])
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

    def test_active_check(self):
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        # test standard scheduler job run of active job
        job = ScheduledJob(name="test_active", task="test",
                           schedule="0 0 * * *")
        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
        job = db.session.merge(job)

        kdict = {"job_id": job.id}
        resp = test_task(**kdict)
        self.assertEquals(len(resp.split()), 6)
        self.assertEquals(resp.split()[-1], 'Test')

        # test standard scheduler job run of inactive job
        job = ScheduledJob(id=999, name="test_inactive", active=False,
                           task="test", schedule="0 0 * * *")
        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
        job = db.session.merge(job)

        kdict = {"job_id": job.id}
        resp = test_task(**kdict)
        self.assertEquals(len(resp.split()), 4)
        self.assertEquals(resp.split()[-1], 'inactive.')

        # test manual override run of inactive job
        kdict['manual_run'] = True
        resp = test_task(**kdict)
        self.assertEquals(len(resp.split()), 6)
        self.assertEquals(resp.split()[-1], 'Test')

    def test_job_trigger(self):
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        # test standard task
        job = ScheduledJob(name="test_trig", task="test", schedule="0 0 * * *")

        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
        job = db.session.merge(job)

        resp = self.client.post('/api/scheduled_job/{}/trigger'.format(job.id))

        self.assert200(resp)
        self.assertEquals(resp.json['message'].split()[-1], 'Test')

        # test task w/ args + kwargs
        alist = ["arg1", "arg2", "arg3"]
        kdict = {"kwarg1": 12345, "kwarg2": "abcde"}
        job = ScheduledJob(name="test_trig_2", task="test_args", kwargs=kdict,
                           args=",".join(alist), schedule="0 0 * * *")

        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
        job = db.session.merge(job)

        resp = self.client.post('/api/scheduled_job/{}/trigger'.format(job.id))
        self.assert200(resp)

        msg = resp.json['message'].split(". ")[1].split("|")
        self.assertEquals(msg[0].split(","), alist)
        kdict['manual_run'] = True
        kdict['job_id'] = job.id
        self.assertEquals(json.loads(msg[1]), kdict)

        db.session.close_all()
