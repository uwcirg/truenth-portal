"""Tasks module

All tasks run via external message queue (via celery) are defined
within.

NB: a celery worker must be started for these to ever return.  See
`celery_worker.py`

"""
import requests
from celery.utils.log import get_task_logger
from .extensions import celery

logger = get_task_logger(__name__)


@celery.task
def add(x, y):
    return x + y

@celery.task
def post_request(url, data):
    """Wrap requests.post for asyncronous posts"""
    return requests.post(url, data=data)
