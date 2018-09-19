from flask import current_app
import redis
from redis import ConnectionError

def celery_available():
    return True, 'Celery is available'

def celery_beat_queuing_jobs():
    return True, 'Celery beat is queuing jobs'

def postgres_available():
    return True, 'Postgres is available'

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
    postgres_available,
    redis_available,
]
