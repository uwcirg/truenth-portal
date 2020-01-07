"""API to record and track seconds since last request"""
from flask import current_app
import redis


def _connection():
    # Documented to be pooled at the library level
    return redis.Redis.from_url(current_app.config['REDIS_URL'])


KEY = 'Usage Tracker'


def mark_usage():
    conn = _connection()
    conn.set(name=KEY, value="ping")


def last_usage():
    conn = _connection()
    return conn.object(key=KEY, infotype='idletime')
