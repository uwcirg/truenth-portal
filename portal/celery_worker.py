#!/usr/bin/env python
"""Script to launch the celery worker

The celery worker is necessary to run any celery tasks, and requires
its own flask application instance to create the context necessary for
the flask background tasks to run.

Launch in the same virtual environment via

  $ celery worker -A portal.celery_worker.celery --loglevel=info

"""
from .app import create_app
from .database import db
from .extensions import celery
from .models.scheduled_job import ScheduledJob
import tasks

assert celery  # silence pyflake warning

app = create_app()
app.app_context().push()


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Configure scheduled jobs in Celery"""
    # create test task if non-existent
    if not ScheduledJob.query.filter_by(name="__test_celery__").first():
        test_job = ScheduledJob(name="__test_celery__", task="test",
                                schedule="0 * * * *", active=True)
        db.session.add(test_job)
        db.session.commit()
        test_job = db.session.merge(test_job)

    # add all tasks to Celery
    for job in ScheduledJob.query.filter_by(active=True):
        task = getattr(tasks, job.task, None)
        if task:
            args_in = job.args.split(',') if job.args else []
            kwargs_in = job.kwargs or {}
            sender.add_periodic_task(job.crontab_schedule(),
                                     task.s(*args_in,
                                            job_id=job.id,
                                            **kwargs_in))
