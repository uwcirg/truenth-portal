from datetime import datetime
from flask import url_for
from mock import Mock, patch
import redis
from tests import TestCase

from portal.views.healthcheck import (
    celery_available,
    celery_beat_available,
    postgresql_available,
    redis_available,
)


class TestHealthcheck(TestCase):
    """Health check module and view tests"""

    @patch('portal.views.healthcheck.requests.get')
    def test_celery_available_succeeds_when_celery_test_succeeds(
        self,
        requests_mock
    ):
        requests_mock.return_value.ok = True
        results = celery_available()
        assert results[0] is True

    @patch('portal.views.healthcheck.requests.get')
    def test_celery_available_fails_when_celery_test_fails(
        self,
        requests_mock
    ):
        requests_mock.return_value.ok = False
        requests_mock.return_value.status_code = 500

        results = celery_available()
        assert results[0] is False

    @patch('portal.views.healthcheck.redis')
    def test_celery_beat_available_fails_when_redis_var_none(
        self,
        redis_mock
    ):
        redis_mock.from_url.return_value.get.return_value = None
        results = celery_beat_available()
        assert results[0] is False

    @patch('portal.views.healthcheck.redis')
    def test_celery_beat_available_succeeds_when_redis_var_set(
        self,
        redis_mock
    ):
        redis_mock.from_url.return_value.get.return_value = \
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

    @patch('portal.views.healthcheck.redis')
    def test_redis_available_succeeds_when_ping_successful(
        self,
        redis_mock
    ):
        redis_mock.from_url.return_value.ping.return_value = True
        results = redis_available()
        assert results[0] is True

    @patch('portal.views.healthcheck.redis')
    def test_redis_available_fails_when_ping_throws_exception(
        self,
        redis_mock
    ):
        redis_mock.from_url.return_value.ping.side_effect = \
            redis.ConnectionError()
        results = redis_available()
        assert results[0] is False
