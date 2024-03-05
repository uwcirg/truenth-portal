from datetime import datetime

from mock import Mock, patch
import pytest
import redis

from portal.views.healthcheck import (
    celery_available,
    celery_beat_available,
    postgresql_available,
    redis_available,
)
from tests import TestCase


class TestHealthcheck(TestCase):
    """Health check module and view tests"""

    def test_celery_available_succeeds_when_celery_test_success(self):
        results = celery_available()
        assert results[0] is True

    @pytest.mark.skip(reason="not mocking correctly - todo, fixme")
    @patch('portal.views.healthcheck.celery_available')
    def test_celery_available_fails_when_celery_ping_fails(
            celery_available_mock):
        celery_available_mock.return_value = False

        results = celery_available()
        assert results[0] is False

    @patch('portal.views.healthcheck.create_redis')
    def test_celery_beat_available_fails_when_redis_var_none(
        self,
        create_redis_mock
    ):
        create_redis_mock.return_value.get.return_value = None
        results = celery_beat_available()
        assert results[0] is False

    @patch('portal.views.healthcheck.create_redis')
    def test_celery_beat_available_succeeds_when_redis_var_set(
        self,
        create_redis_mock
    ):
        create_redis_mock.return_value.get.return_value = \
            str(datetime.now())
        results = celery_beat_available()
        assert results[0] is True

    @patch('portal.views.healthcheck.db')
    def test_postgresql_available_succeeds_when_query_successful(
        self,
        db_mock
    ):
        db_mock.engine.execute = Mock(return_value=True)
        results = postgresql_available()
        assert results[0] is True

    @patch('portal.views.healthcheck.db')
    def test_postgresql_available_fails_when_query_exception(
        self,
        db_mock
    ):
        db_mock.engine.execute.side_effect = Mock(
            side_effect=Exception('Something went wrong')
        )
        results = postgresql_available()
        assert results[0] is False

    @patch('portal.views.healthcheck.create_redis')
    def test_redis_available_succeeds_when_ping_successful(
        self,
        create_redis_mock
    ):
        create_redis_mock.return_value.ping.return_value = True
        results = redis_available()
        assert results[0] is True

    @patch('portal.views.healthcheck.create_redis')
    def test_redis_available_fails_when_ping_throws_exception(
        self,
        create_redis_mock
    ):
        create_redis_mock.return_value.ping.side_effect = \
            redis.ConnectionError()
        results = redis_available()
        assert results[0] is False

    def test_successful_healthcheck_has_200_status_code(self):
        # Initialize the healthcheck
        self.app.healthcheck.checkers = [success_health_check]

        # Call the healthcheck API
        response = self.client.get('/healthcheck')

        # assert response
        assert 200 == response.status_code

        json = response.json
        assert json['status'] == "success"

        results = json['results']
        assert len(results) == 1
        assert results[0]['checker'] == 'success_health_check'
        assert results[0]['passed'] is True

    def test_failed_healthcheck_has_200_status_code(self):
        # Initialize the healthcheck
        self.app.healthcheck.checkers = [failure_health_check]

        # Call the healthcheck API
        response = self.client.get('/healthcheck')

        # assert response
        assert 200 == response.status_code

        json = response.json
        assert json['status'] == "failure"

        results = json['results']
        assert len(results) == 1
        assert results[0]['checker'] == 'failure_health_check'
        assert results[0]['passed'] is False


def success_health_check():
    return True, 'Success'


def failure_health_check():
    return False, 'Failure'
