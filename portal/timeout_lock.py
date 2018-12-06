import time
import redis

from flask import current_app


class LockTimeout(BaseException):
    """Exception raised when wait for TimeoutLock exceeds timeout"""
    pass


class TimeoutLock(object):
    def __init__(self, key, expires=60, timeout=10):
        """
        Distributed locking using Redis SETNX and GETSET.

        Usage::

            with Lock('my_lock'):
                print "Critical section"

        :param expires: Any existing lock older than ``expires`` seconds is
          considered invalid in order to detect crashed clients. This value
          must be higher than it takes the critical section to execute.
        :param timeout: If another client has already obtained the lock, sleep
          for a maximum of ``timeout`` seconds before giving up. A value of 0
          means we never wait.

        """

        self.key = key
        self.timeout = timeout
        self.expires = expires
        self.redis = redis.StrictRedis.from_url(
            current_app.config['REDIS_URL'])

    def __enter__(self):
        timeout = self.timeout
        while timeout >= 0:
            expires = time.time() + self.expires + 1

            if self.redis.setnx(self.key, expires):
                # lock acquired; enter critical section
                return

            current_value = self.redis.get(self.key)

            # Found an expired lock and nobody beat us to replacing it
            if current_value and float(current_value) < time.time() and \
                self.redis.getset(self.key, expires) == current_value:
                    return

            timeout -= 1
            time.sleep(1)

        raise LockTimeout("Timeout whilst waiting for lock {}".format(
            self.key))

    def __exit__(self, exc_type, exc_value, traceback):
        self.redis.delete(self.key)
