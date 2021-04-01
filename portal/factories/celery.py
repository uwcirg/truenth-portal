from celery import Celery, signals
import logging
import sys

from ..extensions import db

__celery = None


@signals.setup_logging.connect
def on_setup_logging(**kwargs):
    logger = logging.getLogger('celery')
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.propagate = True
    logger = logging.getLogger('celery.app.trace')
    logger.setLevel(logging.INFO)
    logger.propagate = True


def create_celery(app):
    global __celery
    if __celery:
        return __celery

    app.logger.debug("Create celery w/ backends {} & {}".format(
        app.config['CELERY_RESULT_BACKEND'],
        app.config['SQLALCHEMY_DATABASE_URI']))

    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['BROKER_URL'],
    )
    celery.conf.update(app.config)

    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                db.session = db.create_scoped_session()
                try:
                    response = TaskBase.__call__(self, *args, **kwargs)
                finally:
                    db.session.remove()
                return response

    celery.Task = ContextTask

    __celery = celery
    return __celery
