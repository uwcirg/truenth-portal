"""Scheduled Job module"""
from datetime import datetime
from random import randint
import re

from celery.schedules import crontab
from flask import current_app, url_for

from ..database import db
from ..factories.celery import create_celery


class ScheduledJob(db.Model):
    """ScheduledJob model for storing scheduled runs of celery tasks"""
    __tablename__ = 'scheduled_jobs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    task = db.Column(db.Text, nullable=False)
    args = db.Column(db.Text, nullable=True)
    kwargs = db.Column(db.JSON, nullable=True)
    _schedule = db.Column('schedule', db.Text, nullable=False)
    active = db.Column(db.Boolean(), nullable=False, server_default='1')
    last_runtime = db.Column(db.DateTime, nullable=True)
    last_status = db.Column(db.Text)

    def __str__(self):
        return "scheduled_job {0.name} ({0.task}: {0._schedule})".format(self)

    @property
    def schedule(self):
        return self._schedule

    @schedule.setter
    def schedule(self, sc):
        # schedule must match cron schedule pattern * * * * *
        # with the option of using an 'r' in the minutes column
        # to request random minute generation
        cron_format = r'([\*\d,-\/,r]+)\s([\*\d,-\/]+)\s([\*\d,-\/]+)' \
                      r'\s([\*\d,-\/]+)\s([\*\d,-\/]+)$'
        if not sc or not re.match(cron_format, sc):
            raise Exception("schedule must be in valid cron format")
        if sc.startswith('r'):
            sc = str(randint(0, 59)) + sc[1:]
        self._schedule = sc

    @classmethod
    def from_json(cls, data):
        instance = cls()
        return instance.update_from_json(data)

    def update_from_json(self, data):
        if 'name' not in data:
            raise ValueError("missing required name field")
        self.name = data['name']
        for attr in ('task', 'schedule'):
            if data.get(attr):
                setattr(self, attr, data[attr])
            elif not getattr(self, attr, None):
                raise ValueError("missing required {} value".format(attr))
        for attr in ('args', 'kwargs', 'active'):
            if data.get(attr, None) is not None:
                setattr(self, attr, data[attr])
        return self

    def as_json(self):
        d = {}
        d['id'] = self.id
        d['resourceType'] = 'ScheduledJob'
        d['name'] = self.name
        d['task'] = self.task
        d['args'] = self.args
        d['kwargs'] = self.kwargs
        d['schedule'] = self.schedule
        d['active'] = self.active
        return d

    def crontab_schedule(self):
        svals = self.schedule.split()
        return crontab(
            minute=svals[0],
            hour=svals[1],
            day_of_month=svals[2],
            month_of_year=svals[3],
            day_of_week=svals[4])

    def trigger(self):
        from .. import tasks
        func = getattr(tasks, self.task, None)
        if func:
            args_in = self.args.split(',') if self.args else []
            kwargs_in = self.kwargs or {}
            kwargs_in['job_id'] = self.id
            kwargs_in['manual_run'] = True
            try:
                celery = create_celery(current_app)
                res = celery.send_task(
                    "portal.tasks.{}".format(self.task),
                    args=args_in, kwargs=kwargs_in)
                result_url = url_for(
                    'portal.task_result', task_id=res.task_id)
                msg = "Task sent to celery; see {} for results".format(
                    result_url, _external=True)
            except Exception as exc:
                msg = ("Unexpected exception in task `{}` (job_id={}):"
                       " {}".format(self.task, self.id, exc))
            return msg
        return 'task {} not found'.format(self.task)


def update_job_status(job_id, runtime=None, status=None):
    if job_id:
        runtime = runtime or datetime.now()
        sj = ScheduledJob.query.get(job_id)
        if sj:
            sj.last_runtime = runtime
            sj.last_status = status
            db.session.add(sj)
            db.session.commit()
            return db.session.merge(sj)


def check_active(job_id):
    sj = ScheduledJob.query.get(job_id)
    return sj.active if sj else False
