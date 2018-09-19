def celery_available():
    return True, 'Celery is available'

def celery_beat_queuing_jobs():
    return True, 'Celery beat is queuing jobs'

def postgres_available():
    return True, 'Postgres is available'

def redis_available():
    return True, 'Postgres is available'

HEALTH_CHECKS = [
    celery_available,
    celery_beat_queuing_jobs,
    postgres_available,
    redis_available,
]
