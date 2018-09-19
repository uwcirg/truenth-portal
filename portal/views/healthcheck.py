from flask import current_app
import redis
from redis import ConnectionError

from ..database import db

def celery_available():
    return True, 'Celery is available'

def celery_beat_queuing_jobs():
    return True, 'Celery beat is queuing jobs'

def postgresql_available():
    try:
        db.session.query("1").from_statement("SELECT 1").all()
        return True, 'PostgreSQL is available'
    except:
        current_app.logger.error('sql alchemy not connected to db')
        return False, 'PostgreSQL is not available'

def redis_available():
    rs = redis.from_url(current_app.config["REDIS_URL"])
    try:
        rs.ping()
        return True, 'Redis is available'
    except ConnectionError:
        current_app.logger.error("Unable to connect to redis.")
        return False, 'Redis is not available'

HEALTH_CHECKS = [
    celery_available,
    celery_beat_queuing_jobs,
    postgresql_available,
    redis_available,
]
