"""Scheduled Job module"""
from celery.schedules import crontab
import re

from .. import tasks
from ..database import db
from ..extensions import celery

class ScheduledJob(db.Model):
    """ORM class for user document upload data

    Capture and store uploaded user documents
    (e.g. patient reports, user avatar images, etc).

    """
    __tablename__ = 'scheduled_jobs'
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.Text, nullable=False)
    args = db.Column(db.Text, nullable=True)
    _schedule = db.Column('schedule', db.Text, nullable=False)
    active = db.Column(db.Boolean(), nullable=False, server_default='1')

    def __str__(self):
        return "scheduled_job {0.id} ({0.task}: {0._schedule})".format(self)


    @property
    def schedule(self):
        return self._schedule


    @schedule.setter
    def schedule(self, s):
    # schedule must match cron schedule pattern * * * * * 
        format = r'([\*\d,-\/]+)\s([\*\d,-\/]+)\s([\*\d,-\/]+)' \
                 r'\s([\*\d,-\/]+)\s([\*\d,-\/]+)$'
        if not s or re.match(format, s):
            raise Exception("schedule must be in valid cron format")
        self._schedule = s

    def crontab_schedule(self):
        svals = self.schedule.split()
        return crontab(
                       minute=svals[0],
                       hour=svals[1],
                       day_of_month=svals[2],
                       month_of_year=svals[3],
                       day_of_week=svals[4]
                      )
