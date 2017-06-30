#!/usr/bin/env python
"""Script to launch the celery worker

The celery worker is necessary to run any celery tasks, and requires
its own flask application instance to create the context necessary for
the flask background tasks to run.

Launch in the same virtual environment via

  $ celery worker -A portal.celery_worker.celery --loglevel=info

"""
from .extensions import celery
assert celery  # silence pyflake warning
from .app import create_app
from .models.scheduled_job import ScheduledJob
import tasks

app = create_app()
app.app_context().push()

@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
	"""Configure scheduled jobs in Celery"""
	for job in ScheduledJob.query.filter_by(active=True):
		task = getattr(tasks, job.task, None)
		if task:
			sender.add_periodic_task(job.crontab_schedule(),
									 task.s(*job.args.split(',')))
