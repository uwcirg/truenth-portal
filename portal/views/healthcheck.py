from datetime import datetime

from celery.exceptions import TimeoutError
from celery.result import AsyncResult
from flask import Blueprint, current_app
import redis
from sqlalchemy import text

from ..database import db
from ..factories.celery import create_celery

HEALTHCHECK_FAILURE_STATUS_CODE = 200

healthcheck_blueprint = Blueprint('healthcheck', __name__)


@healthcheck_blueprint.route('/celery_beat_ping')
def celery_beat_ping():
    """Periodically called by a celery beat task

    Updates the last time we recieved a call to this API.
    This allows us to monitor whether celery beat tasks are running
    """
    rs = redis.StrictRedis.from_url(current_app.config['REDIS_URL'])
    rs.setex(
        name='last_celery_beat_ping',
        time=current_app.config['LAST_CELERY_BEAT_PING_EXPIRATION_TIME'],
        value=str(datetime.utcnow()),
    )
    return 'PONG'

##############################
# Healthcheck functions below
##############################


def celery_available():
    """Determines whether celery is available"""
    x = 1
    y = 1
    celery = create_celery(current_app)

    try:
        from .portal import celery_test

        celery_test_response = celery_test(x, y)
        task_id = celery_test_response.json['task_id']

        try:
            result = AsyncResult(task_id, app=celery).get(timeout=5.0)
        except TimeoutError:
            return False, 'task timed out'

        return int(result) == (x + y), 'Celery is available.'
    except Exception as e:
        return False, 'failed to get celery test result. Error: {}'.format(e)


def celery_beat_available():
    """Determines whether celery beat is available"""
    rs = redis.from_url(current_app.config['REDIS_URL'])

    # Celery beat feeds scheduled jobs (a la cron) to the respective
    # job queues (standard and low priority).  As a monitor, a job
    # exists in each queue to set a respective value in redis with
    # an expiration.

    # If those redis values are present, we assume celery_beat and
    # both queues are functioning properly.
    last_celery_beat_ping = rs.get('last_celery_beat_ping')
    last_celery_beat_ping_low_priority_queue = rs.get(
        'last_celery_beat_ping_low_priority_queue')
    if last_celery_beat_ping and last_celery_beat_ping_low_priority_queue:
        return True, 'Celery beat is available.'

    detail = "both queues timed out"
    if last_celery_beat_ping:
        detail = "low priority queue timed out"
    elif last_celery_beat_ping_low_priority_queue:
        detail = "standard queue timed out"

    return False, f"Celery beat is not available, {detail}."


def postgresql_available():
    """Determines whether postgresql is available"""
    # Execute a simple SQLAlchemy query.
    # If it succeeds we assume postgresql is available.
    # If it fails we assume psotgresql is not available.
    try:
        db.engine.execute(text('SELECT 1'))
        return True, 'PostgreSQL is available.'
    except Exception as e:
        return False, 'failed to connect to postgreSQL. Error: {}'.format(e)


def redis_available():
    """Determines whether Redis is available"""
    # Ping redis. If it succeeds we assume redis
    # is available. Otherwise we assume
    # it's not available
    rs = redis.from_url(current_app.config["REDIS_URL"])
    try:
        rs.ping()
        return True, 'Redis is available.'
    except Exception as e:
        return False, 'Unable to connect to redis. Error {}'.format(e)


# The checks that determine the health
# of this service's dependencies
HEALTH_CHECKS = [
    celery_available,
    celery_beat_available,
    postgresql_available,
    redis_available,
]
