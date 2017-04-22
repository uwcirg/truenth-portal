import redis
import functools
import logging, sys

import gevent.monkey
gevent.monkey.patch_all()

from portal.app import create_app

def filter_session_events(func):
    """Filter out non-session events"""
    def func_wrapper(message):
        if message.get("data", "").startswith(SESSION_KEY_PREFIX):
            return func(message)
    return func_wrapper

@filter_session_events
def session_started(message):
    logging.info(
        "session started: {}".format(
            message['data'].split(SESSION_KEY_PREFIX)[-1]
        ),
    )

@filter_session_events
def session_expired(message):
    logging.info(
        "session expired: {}".format(
            message['data'].split(SESSION_KEY_PREFIX)[-1]
        ),
    )

class SessionMonitor(object):
    _event_handlers = {
        '__keyevent@{DB}__:expired': session_expired,
        '__keyevent@{DB}__:expire': session_started,
    }

    def __init__(self, r, event_handlers=None):
        self.redis = r
        self.db = self.redis.connection_pool.connection_kwargs.get('db', '*')
        self.pubsub = self.redis.pubsub()

        if event_handlers is None:
            event_handlers = self._event_handlers
        self.event_handlers = {k.format(DB=self.db):v for k,v in event_handlers.items()}

        self.pubsub.psubscribe(**self.event_handlers)

    def run(self):
        self.thread = self.pubsub.run_in_thread(sleep_time=0.001)

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
app = create_app()
with app.app_context():
    SESSION_KEY_PREFIX = app.config.get('SESSION_KEY_PREFIX', 'session:')

    session_monitor = SessionMonitor(app.config['SESSION_REDIS'])
    session_monitor.run()
