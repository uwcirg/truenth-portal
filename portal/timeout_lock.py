import time

from flask import current_app
import redis


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
            if (current_value and float(current_value) < time.time() and
                    self.redis.getset(self.key, expires)):
                return

            timeout -= 1
            time.sleep(1)

        current_app.logger.debug("Timeout on lock '{}'".format(self.key))
        raise LockTimeout("Timeout whilst waiting for lock {}".format(
            self.key))

    def __exit__(self, exc_type, exc_value, traceback):
        self.redis.delete(self.key)
        # To avoid interrupting iterative lock use, return truthy
        # value to stop exception propagation - see PEP
        if exc_type is not None:
            error_message = f"{exc_type}"
            if exc_value:
                error_message += f": {exc_value}"
            if traceback:
                error_message += f"; {traceback}"
            current_app.logger.error(error_message)
        return True

    def is_locked(self):
        """Status check - NOT intended to be combined as an atomic check"""
        current_value = self.redis.get(self.key)
        return current_value and float(current_value) >= time.time()


def guarded_task_launch(task, **kwargs):
    """Launch task after obtaining named semaphore key

    Used by expensive tasks that should prevent multiple simultaneous runs.

    :param task: celery task instance to be launched
    :param kwargs: all arguments to include in task launch, plus `lock_key`

    :raises TimeoutLock: if the named lock is unattainable
    :returns: task id on successful launch

    """
    if 'lock_key' not in kwargs:
        raise ValueError("guarded_tasks require a 'lock_key'")

    # raises LockTimeout if unavailable
    with TimeoutLock(key=kwargs['lock_key'], expires=300, timeout=0):
        result = task.apply_async(kwargs=kwargs)

    return result
