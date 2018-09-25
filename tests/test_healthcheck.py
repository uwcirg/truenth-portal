from tests import TestCase

class TestHealthcheck(TestCase):
    """Health check module and view tests"""

    def test_healthcheck_api_succeeds_when_all_available(self):
        
 
    def test_healthcheck_api_fails_with_when_one_api_fails(self):
        

    def test_celery_available_succeeds_when_subprocess_succeeds(self):
        

    def test_celery_available_fails_when_subprocess_fails(self):
        

    def test_celery_beat_ping_sets_date(self):
        

    def test_celery_beat_available_fails_when_not_pinged(self):
        

    def test_celery_beat_available_succeeds_when_pinged(self):
        

    def test_celery_beat_available_fails_when_ping_expires(self):
        

    def test_postgresql_available_succeeds_when_query_successful(self):
        

    def test_postgresql_available_fails_when_query_exception(self):
        

    def test_redis_available_succeeds_when_ping_successful(self):
        

    def test_redis_available_fails_when_ping_throws_exception(self):
        

