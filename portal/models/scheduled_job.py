"""Scheduled Job module"""
from celery.schedules import crontab
from datetime import datetime
import re

from ..database import db


class ScheduledJob(db.Model):
    """ORM class for user document upload data

    Capture and store uploaded user documents
    (e.g. patient reports, user avatar images, etc).

    """
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
        format = r'([\*\d,-\/]+)\s([\*\d,-\/]+)\s([\*\d,-\/]+)' \
                 r'\s([\*\d,-\/]+)\s([\*\d,-\/]+)$'
        if not sc or not re.match(format, sc):
            raise Exception("schedule must be in valid cron format")
        self._schedule = sc

    @classmethod
    def from_json(cls, data):
        if 'name' not in data:
            raise ValueError("missing required name field")
        job = ScheduledJob.query.filter_by(name=data['name']).first()
        if not job:
            job = cls()
            job.name = data['name']
        for attr in ('task', 'schedule'):
            if data.get(attr):
                setattr(job, attr, data[attr])
            elif not getattr(job, attr, None):
                raise ValueError("missing required {} value".format(attr))
        for attr in ('args', 'kwargs', 'active'):
            if data.get(attr, None) is not None:
                setattr(job, attr, data[attr])
        return job

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
        d['last_runtime'] = self.last_runtime
        d['last_status'] = self.last_status
        return d

    def crontab_schedule(self):
        svals = self.schedule.split()
        return crontab(
                       minute=svals[0],
                       hour=svals[1],
                       day_of_month=svals[2],
                       month_of_year=svals[3],
                       day_of_week=svals[4]
                      )

    def trigger(self):
        from .. import tasks
        func = getattr(tasks, self.task, None)
        if func:
            args_in = self.args.split(',') if self.args else []
            kwargs_in = self.kwargs or {}
            return func(*args_in, job_id=self.id, **kwargs_in)
        return 'task {} not found'.format(self.task)


def update_job(job_id, runtime=None, status=None):
    if job_id:
        runtime = runtime or datetime.now()
        sj = ScheduledJob.query.get(job_id)
        if sj:
            sj.last_runtime = runtime
            sj.last_status = status
            db.session.add(sj)
            db.session.commit()
            return db.session.merge(sj)
