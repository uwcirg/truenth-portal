from multiprocessing import Lock

from contextlib import contextmanager


class TimeoutLock(object):
    """Wrap multiprocessing lock in context manager

    Usage:
        lock = TimeoutLock()

        with lock.acquire_timeout(3) as result:
            if result:
                print('got the lock')
                # do something ....
            else:
                print('timeout: lock not available')
                # do something else ...

    """
    def __init__(self):
        self._lock = Lock()

    def acquire(self, blocking=True, timeout=-1):
        return self._lock.acquire(blocking, timeout)

    @contextmanager
    def acquire_timeout(self, timeout):
        result = self._lock.acquire(timeout=timeout)
        yield result
        if result:
            self._lock.release()

    def release(self):
        self._lock.release()

