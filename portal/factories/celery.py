
from celery import Celery

from ..extensions import db

__celery = None


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
