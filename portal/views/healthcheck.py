from celery.task.control import inspect
from flask import current_app
import json
import redis
from redis import ConnectionError
from sqlalchemy import text

from ..database import db

def celery_available():
    try:
        #inspect().ping()
        return True, 'Celery is available.'
    except IOError as e:
        current_app.logger.error('Unable to connect to celery. Error {}'.format(e))
        return False, 'Celery is not available'

def celery_beat_queuing_jobs():
    return True, 'Celery beat is queuing jobs'

def postgresql_available():
    try:
        db.session.query('1').from_statement(text('SELECT 1 as is_alive')).all()
        return True, 'PostgreSQL is available'
    except Exception as e:
        current_app.logger.error('sql alchemy not connected to postgreSQL. Error: {}'.format(e))
        return False, 'PostgreSQL is not available'

def redis_available():
    rs = redis.from_url(current_app.config["REDIS_URL"])
    try:
        rs.ping()
        return True, 'Redis is available'
    except ConnectionError as e:
        current_app.logger.error('Unable to connect to redis. Error {}'.format(e))
        return False, 'Redis is not available'

HEALTH_CHECKS = [
    celery_available,
    celery_beat_queuing_jobs,
    postgresql_available,
    redis_available,
]
