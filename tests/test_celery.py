"""Unit test module for portal views"""
import pytest
from flask import url_for


def test_simple_request(client, initialized_db):
    """Not a celery test - just a trite example of using the client fixture"""
    assert client.get('/').status_code == 200


@pytest.mark.skip(reason="locking up with celery fixtures")
def test_celery_add(celery_app, celery_worker, client, initialized_db):
    """Test a task in the default queue"""
    x = 151
    y = 99

    # Call the worker task directly
    from portal.tasks import add
    assert add.delay(x, y).get() == x + y

    # Call the worker task from the exposed view on flask client
    response = client.get(url_for('portal.celery_test', x=x, y=y))
    assert response.status_code == 200
    assert response.json['result'] == x + y


@pytest.mark.skip(reason="locking up with celery fixtures")
def test_celery_info(celery_app, celery_worker):
    """Test a task in the low-priority queue"""
    from portal.tasks import info
    assert "BROKER_URL" in info.delay().get()
