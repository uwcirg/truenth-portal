"""Scheduled Job module"""
from celery.schedules import crontab
from datetime import datetime
import re

from ..database import db
from ..extensions import celery


class ScheduledJob(db.Model):
    """ORM class for user document upload data

    Capture and store uploaded user documents
    (e.g. patient reports, user avatar images, etc).

    """
    __tablename__ = 'scheduled_jobs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    task = db.Column(db.Text, nullable=False)
    args = db.Column(db.Text, nullable=True)
    kwargs = db.Column(db.JSON, nullable=True)
    _schedule = db.Column('schedule', db.Text, nullable=False)
    active = db.Column(db.Boolean(), nullable=False, server_default='1')
    last_runtime = db.Column(db.DateTime, nullable=True)

    def __str__(self):
        return "scheduled_job {0.id} ({0.task}: {0._schedule})".format(self)

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

    def crontab_schedule(self):
        svals = self.schedule.split()
        return crontab(
                       minute=svals[0],
                       hour=svals[1],
                       day_of_month=svals[2],
                       month_of_year=svals[3],
                       day_of_week=svals[4]
                      )

def update_runtime(job_id, runtime=None):
    runtime = runtime or datetime.now()
    sj = ScheduledJob.query.get(job_id)
    if sj:
        sj.last_runtime = runtime
        db.session.add(sj)
        db.session.commit()
        return db.session.merge(sj)
