#!/usr/bin/env python
"""Script to launch the celery worker, using a Flask app configured for testing

The celery worker is necessary to run any celery tasks, and requires
its own flask application instance to create the context necessary for
the flask background tasks to run.

Launch in the same virtual environment via

  $ celery worker --app portal.celery_test_worker.celery --loglevel info

"""
from config.config import TestConfig
from factories.celery import create_celery
from factories.app import create_app


# celery app for testing
test_app = create_app(TestConfig)
test_celery = create_celery(test_app)
test_app.app_context().push()
