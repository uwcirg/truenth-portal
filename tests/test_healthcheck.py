from datetime import datetime
from flask import url_for
from mock import Mock, patch
from redis
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
        requests.mock.return_value.status_code = 500

        results = celery_available()
        assert results[0] is False

    def test_celery_beat_available_fails_when_not_pinged(self):
        results = celery_beat_available()
        assert results[0] is False

    def test_celery_beat_available_succeeds_when_pinged(self):
        response = self.client.get(url_for('healthcheck.celery_beat_ping'))
        assert response.status_code == 200
        assert response.get_data(as_text=True) == 'PONG'

        results = celery_beat_available()
        assert results[0] is True

    def test_celery_beat_available_fails_when_ping_expires(self):
        response = self.client.get(url_for('healthcheck.celery_beat_ping'))
        assert response.status_code == 200
        assert response.get_data(as_text=True) == 'PONG'

        # expire the last ping
        rs = redis.from_url(app.config['REDIS_URL'])
        rs.delete('celery_beat_available')

        response = celery_beat_available()
        assert response[0] is False

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
        redis_connection_mock = Mock()
        redis_connection_mock.ping = Mock(
            side_effect=redis.ConnectionError()
        )
        redis_mock.from_url.return_value = redis_connection_mock
        results = redis_available()
        assert results[0] is False
