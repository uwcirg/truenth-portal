#!/usr/bin/env python
"""Script to launch the celery worker

The celery worker is necessary to run any celery tasks, and requires
its own flask application instance to create the context necessary for
the flask background tasks to run.

Launch in the same virtual environment via

  $ celery worker -A portal.celery_worker.celery --loglevel=info

"""
from .database import db
from config.config import TestConfig
from factories.celery import create_celery
from factories.app import create_app
from .models.scheduled_job import ScheduledJob


app = create_app()
celery = create_celery(app)
app.app_context().push()

# celery app for testing
test_app = create_app(TestConfig)
test_celery = create_celery(test_app)
test_app.app_context().push()


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Configure scheduled jobs in Celery"""
    import tasks
    tasks.logger.info("Starting ScheduledJob load...")
    # create test task if non-existent
    if not ScheduledJob.query.filter_by(name="__test_celery__").first():
        test_job = ScheduledJob(name="__test_celery__", task="test",
                                schedule="0 * * * *", active=True)
        db.session.add(test_job)
        db.session.commit()
        test_job = db.session.merge(test_job)

    # add all tasks to Celery
    tasks.logger.info("ScheduledJobs found: {}".format(ScheduledJob.query.count()))
    for job in ScheduledJob.query.all():
        task = getattr(tasks, job.task, None)
        if task:
            tasks.logger.info("Adding task (id=`{}`, task=`{}` "
                        "to CeleryBeat".format(job.id, job.task))
            args_in = job.args.split(',') if job.args else []
            kwargs_in = job.kwargs or {}
            kwargs_in['job_id'] = job.id
            try:
                sender.add_periodic_task(job.crontab_schedule(),
                                         task.s(*args_in, **kwargs_in))
            except Exception as exc:
                tasks.logger.error(exc)
