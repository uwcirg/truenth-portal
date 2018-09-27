from datetime import datetime
from flask import Blueprint, current_app
import redis
from sqlalchemy import text

from ..factories.celery import create_celery
from ..database import db


healthcheck_blueprint = Blueprint('healthcheck', __name__)


@healthcheck_blueprint.route('/celery_beat_ping')
def celery_beat_ping():
    """Periodically called by a celery beat task

    Updates the last time we recieved a call to this API.
    This allows us to monitor whether celery beat tasks are running
    """
    rs = redis.StrictRedis.from_url(current_app.config['REDIS_URL'])
    rs.setex(
        'last_celery_beat_ping',
        current_app.config['LAST_CELERY_BEAT_PING_EXPIRATION_TIME'],
        str(datetime.now()),
    )
    return 'PONG'


##############################
# Healthcheck functions below
##############################

def celery_available():
    """Determines whether celery is available"""
    celery = create_celery(current_app)
    result = celery.control.inspect().ping()
    if result:
        return True, 'Celery is available.'
    else:
        return False, 'Celery is not available'


def celery_beat_available():
    """Determines whether celery beat is available"""
    rs = redis.from_url(current_app.config['REDIS_URL'])

    # When celery beat is running it pings
    # our service periodically which sets
    # 'celery_beat_available' in redis. If
    # that variable expires it means
    # we have not received a ping from celery beat
    # within the allowed window and we must assume
    # celery beat is not available
    last_celery_beat_ping = rs.get('last_celery_beat_ping')
    if last_celery_beat_ping:
        return (
            True,
            'Celery beat is available. Last check: {}'.format(
                last_celery_beat_ping
            )
        )

    return False, 'Celery beat is not running jobs'


def postgresql_available():
    """Determines whether postgresql is available"""
    # Execute a simple SQL Alchemy query.
    # If it succeeds we assume postgresql is available.
    # If it fails we assume psotgresql is not available.
    try:
        db.engine.execute(text('SELECT 1'))
        return True, 'PostgreSQL is available'
    except Exception as e:
        current_app.logger.error(
            'sql alchemy not connected to postgreSQL. Error: {}'.format(e)
        )
        return False, 'PostgreSQL is not available'


def redis_available():
    """Determines whether Redis is available"""
    # Ping redis. If it succeeds we assume redis
    # is available. Otherwise we assume
    # it's not available
    rs = redis.from_url(current_app.config["REDIS_URL"])
    try:
        rs.ping()
        return True, 'Redis is available'
    except Exception as e:
        current_app.logger.error(
            'Unable to connect to redis. Error {}'.format(e)
        )
        return False, 'Redis is not available'


# The checks that determine the health
# of this service's dependencies
HEALTH_CHECKS = [
    celery_available,
    celery_beat_available,
    postgresql_available,
    redis_available,
]
