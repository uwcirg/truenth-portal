"""Unit test module for scheduled jobs logic"""

import json

from flask_webtest import SessionScope
import pytest

from portal.extensions import db
from portal.models.role import ROLE
from portal.models.scheduled_job import ScheduledJob
from portal.tasks import test as task_test
from sqlalchemy.orm import session
from tests import TestCase


class TestScheduledJob(TestCase):
    """Scheduled Job tests"""

    def test_schedule(self):
        schedule = "45 * * * *"
        sj = ScheduledJob(name="test_sched", task="test",
                          schedule=schedule, active=True)
        sjc = sj.crontab_schedule()
        assert 45 in sjc.minute
        assert len(sjc.hour) == 24

        invalid_schedule = "monday to friday"
        with pytest.raises(Exception):
            sj.schedule = invalid_schedule
        invalid_schedule = "* * * * * *"
        with pytest.raises(Exception):
            sj.schedule = invalid_schedule

    def test_random_schedule(self):
        schedule = "r * * * *"
        sj = ScheduledJob(
            name="rando", task="test", schedule=schedule, active=True)
        sjc = sj.crontab_schedule()
        assert len(sjc.minute) == 1
        assert sjc.minute.pop() in range(0, 60)
        assert len(sjc.hour) == 24

    def test_job_upsert(self):
        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()

        # test new job POST
        data = {"name": "test_upsert",
                "task": "test",
                "schedule": "* * * * *"}
        resp = self.client.post(
            '/api/scheduled_job',
            content_type='application/json',
            data=json.dumps(data))
        assert resp.status_code == 200
        job_id = resp.json['id']
        assert resp.json['schedule'] == '* * * * *'

        # POST of an existing should raise a 400
        resp = self.client.post(
            '/api/scheduled_job',
            content_type='application/json',
            data=json.dumps(data))
        assert resp.status_code == 400

        # test existing job PUT
        data2 = {'schedule': "0 0 0 0 0"}
        resp = self.client.put(
            '/api/scheduled_job/{}'.format(job_id),
            content_type='application/json',
            data=json.dumps(data2))
        assert resp.status_code == 200
        assert resp.json['name'] == data['name']
        assert resp.json['schedule'] == '0 0 0 0 0'

    def test_job_get(self):
        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()

        job = ScheduledJob(name="test_get", task="test", schedule="0 0 * * *")
        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
            job = db.session.merge(job)
            job_id = job.id

        resp = self.client.get('/api/scheduled_job/{}'.format(job_id))
        assert resp.status_code == 200
        assert resp.json['task'] == 'test'

        resp = self.client.get('/api/scheduled_job/999')
        assert resp.status_code == 404

    def test_job_delete(self):
        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()

        job = ScheduledJob(name="test_del", task="test", schedule="0 0 * * *")
        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
            job = db.session.merge(job)
            job_id = job.id

        resp = self.client.delete('/api/scheduled_job/{}'.format(job_id))
        assert resp.status_code == 200
        assert not ScheduledJob.query.all()

        resp = self.client.delete('/api/scheduled_job/999')
        assert resp.status_code == 404

    def test_active_check(self):
        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()

        # test standard scheduler job run of active job
        job = ScheduledJob(name="test_active", task="test",
                           schedule="0 0 * * *")
        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
        job = db.session.merge(job)

        kdict = {"job_id": job.id}
        resp = task_test(**kdict)
        assert len(resp.split()) == 6
        assert resp.split()[-1] == 'Test'

        # test standard scheduler job run of inactive job
        job = ScheduledJob(id=999, name="test_inactive", active=False,
                           task="test", schedule="0 0 * * *")
        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
        job = db.session.merge(job)

        kdict = {"job_id": job.id}
        resp = task_test(**kdict)
        assert len(resp.split()) == 4
        assert resp.split()[-1] == 'inactive.'

        # test manual override run of inactive job
        kdict['manual_run'] = True
        resp = task_test(**kdict)
        assert len(resp.split()) == 6
        assert resp.split()[-1] == 'Test'

    def test_job_trigger(self):
        self.promote_user(role_name=ROLE.ADMIN.value)
        self.login()

        # test standard task
        job = ScheduledJob(name="test_trig", task="test", schedule="0 0 * * *")

        with SessionScope(db):
            db.session.add(job)
            db.session.commit()
        job = db.session.merge(job)

        resp = self.client.post('/api/scheduled_job/{}/trigger'.format(job.id))

        assert resp.status_code == 200
        assert resp.json['message'].startswith('Task sent to celery')

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
        assert resp.status_code == 200

        session.close_all_sessions()
