#!/usr/bin/env python
"""Script to launch the celery worker

The celery worker is necessary to run any celery tasks, and requires
its own flask application instance to create the context necessary for
the flask background tasks to run.

Launch in the same virtual environment via

  $ celery worker -A portal.celery_worker.celery --loglevel=info

"""
from . import tasks
from .database import db
from .factories.app import create_app
from .factories.celery import create_celery
from .models.scheduled_job import ScheduledJob

app = create_app()
celery = create_celery(app)
app.app_context().push()


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Configure scheduled jobs in Celery"""
    from .tasks import logger
    logger.info("Starting ScheduledJob load...")

    # As this fires from a celery worker, obtain a scoped session to free
    # the resource, which otherwise prevents test runs from purging the db
    with db.scoped_session as session:
        # create test task if non-existent
        if not session.query(ScheduledJob).filter_by(
                name="__test_celery__").first():
            test_job = ScheduledJob(name="__test_celery__", task="test",
                                    schedule="0 * * * *", active=True)
            session.add(test_job)
            session.commit()

        # add all tasks to Celery
        logger.info("ScheduledJobs found: {}".format(
            ScheduledJob.query.count()))
        for job in session.query(ScheduledJob).all():
            task = getattr(tasks, job.task, None)
            if not task:
                continue

            logger.info("Adding task (id=`{}`, task=`{}` "
                        "to CeleryBeat".format(job.id, job.task))
            args_in = job.args.split(',') if job.args else []
            kwargs_in = job.kwargs or {}
            kwargs_in['job_id'] = job.id
            try:
                sender.add_periodic_task(job.crontab_schedule(),
                                         task.s(*args_in, **kwargs_in))
            except Exception as exc:
                logger.error(exc)
