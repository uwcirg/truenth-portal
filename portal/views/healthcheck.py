from datetime import datetime, timedelta
from flask import Blueprint, current_app
import os
import redis
from redis import ConnectionError
from sqlalchemy import text
import subprocess

from ..database import db


healthcheck_blueprint = Blueprint('healthcheck', __name__)
last_celery_beat_ping = None

@healthcheck_blueprint.route('/celery_beat_ping')
def celery_beat_ping():
    """Periodically called by a celery beat task
    
    Updates the last time we recieved a call to this API.
    This allows us to monitor whether celery beat tasks are running
    """
    global last_celery_beat_ping
    last_celery_beat_ping = datetime.now()
    return 'PONG'


##############################
# Healthcheck functions below
##############################

def celery_available():
    FNULL = open(os.devnull, 'w')
    code = subprocess.call([
            'celery',
            '-A', 'portal.celery_worker.celery',
            'inspect', 'ping'
        ],
        stdout=FNULL, # Don't output to console
        stderr=subprocess.STDOUT
    )
    if code == 0:
        return True, 'Celery is available.'
    else:
        current_app.logger.error(
            'Unable to connect to celery. Exit code {}'.format(code)
        )
        return False, 'Celery is not available'

def celery_beat_available():
    if last_celery_beat_ping:
        # The interval celery beat pings the celery_beat_ping API
        ping_interval = current_app.config['CELERY_BEAT_PING_INTERVAL_SECONDS']

        # The number of times we can miss a ping before we fail
        missed_beats_before_fail = \
            current_app.config['CELERY_BEAT_MISSED_PINGS_BEFORE_FAIL']

        # The maximum amount of time we can go
        # without a ping and still succeed
        threshold = timedelta(
            seconds=(ping_interval * missed_beats_before_fail)
        )
        time_since_last_beat = \
            datetime.now() - last_celery_beat_ping

        if time_since_last_beat <= threshold:
            return True, 'Celery beat is available. Last check: {}'.format(last_celery_beat_ping)
    
    return False, "Celery beat is not running jobs. Last check: {}".format(last_celery_beat_ping)

def postgresql_available():
    try:
        db.engine.execute(text('SELECT 1'))
        return True, 'PostgreSQL is available'
    except Exception as e:
        current_app.logger.error(
            'sql alchemy not connected to postgreSQL. Error: {}'.format(e)
        )
        return False, 'PostgreSQL is not available'

def redis_available():
    rs = redis.from_url(current_app.config["REDIS_URL"])
    try:
        rs.ping()
        return True, 'Redis is available'
    except ConnectionError as e:
        current_app.logger.error(
            'Unable to connect to redis. Error {}'.format(e)
        )
        return False, 'Redis is not available'

HEALTH_CHECKS = [
    celery_available,
    celery_beat_available,
    postgresql_available,
    redis_available,
]
