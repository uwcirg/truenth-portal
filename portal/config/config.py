"""Configuration"""
import os
import redis

from portal.models.role import ROLE

SITE_CFG = 'site.cfg'


def best_sql_url():
    """Return compliant sql url from available environment variables"""
    env = os.environ
    if 'PGDATABASE' in env:
        return (
            'postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}/{PGDATABASE}'.format(
                PGUSER=env.get('PGUSER'), PGPASSWORD=env.get('PGPASSWORD'),
                PGHOST=env.get('PGHOST', 'localhost'),
                PGDATABASE=env.get('PGDATABASE')))


def testing_sql_url():
    """
    Return compliant sql url from available environment variables

    If tests are being run with pytest-xdist workers,
    a pre-existing database will be required for each worker,
    suffixed with the worker index.
    """

    test_db_url = os.environ.get(
        'SQLALCHEMY_DATABASE_TEST_URI',
        "postgresql://test_user:4tests_only@localhost/portal_unit_tests"
    )

    worker_name = os.environ.get('PYTEST_XDIST_WORKER')
    if not worker_name:
        return test_db_url

    worker_index = "".join(char for char in worker_name if char.isdigit())
    return test_db_url + worker_index


class BaseConfig(object):
    """Base configuration - override in subclasses"""
    TESTING = False

    SERVER_NAME = os.environ.get(
        'SERVER_NAME',
        'localhost'
    )

    # Allow Heroku env vars to override most defaults
    # NB: The value of REDIS_URL may change at any point
    REDIS_URL = os.environ.get(
        'REDIS_URL',
        'redis://localhost:6379/0'
    )

    ANONYMOUS_USER_ACCOUNT = True
    BROKER_URL = os.environ.get(
        'BROKER_URL',
        REDIS_URL
    )
    CELERY_RESULT_BACKEND = os.environ.get(
        'CELERY_RESULT_BACKEND',
        REDIS_URL
    )
    REQUEST_CACHE_URL = os.environ.get(
        'REQUEST_CACHE_URL',
        REDIS_URL
    )
    REQUEST_CACHE_EXPIRE = 10

    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 25))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL')
    MAIL_SUPPRESS_SEND = os.environ.get(
        'MAIL_SUPPRESS_SEND',
        str(TESTING)).lower() == 'true'
    CONTACT_SENDTO_EMAIL = os.environ.get('CONTACT_SENDTO_EMAIL')
    ERROR_SENDTO_EMAIL = os.environ.get('ERROR_SENDTO_EMAIL')
    FLUSH_CACHE_ON_SYNC = True

    CELERY_IMPORTS = ('portal.tasks',)
    CELERY_BEAT_HEALTH_CHECK_INTERVAL_SECONDS = 60 * 5 # 5 minutes
    DEBUG = False
    DOGPILE_CACHE_BACKEND = 'dogpile.cache.redis'
    DOGPILE_CACHE_REGIONS = [
        ('assessment_cache_region', 60*60*2),
        ('reporting_cache_region', 60*60*12)]
    SEND_FILE_MAX_AGE_DEFAULT = 60 * 60  # 1 hour, in seconds

    LOG_CACHE_MISS = False
    LOG_FOLDER = os.environ.get('LOG_FOLDER')
    LOG_LEVEL = 'DEBUG'

    OAUTH2_PROVIDER_TOKEN_EXPIRES_IN = 4 * 60 * 60  # units: seconds
    DEFAULT_INACTIVITY_TIMEOUT = 30 * 60  # default inactivity timeout
    PERMANENT_SESSION_LIFETIME = 60 * 60  # defines life of redis session
    SEXUAL_RECOVERY_TIMEOUT = 60 * 60  # SR users get 1 hour

    PIWIK_DOMAINS = ""
    PIWIK_SITEID = 0
    PORTAL_STYLESHEET = 'css/portal.css'
    PRE_REGISTERED_ROLES = [
        'access_on_verify', 'write_only', 'promote_without_identity_challenge']
    PROJECT = "portal"
    SHOW_EXPLORE = True
    SHOW_PROFILE_MACROS = ['ethnicity', 'race']
    SHOW_PUBLIC_TERMS = True
    SHOW_WELCOME = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = best_sql_url()
    SESSION_PERMANENT = True
    SESSION_TYPE = 'redis'

    SESSION_REDIS_URL = os.environ.get(
        'SESSION_REDIS_URL',
        REDIS_URL
    )

    # Todo: create issue @ fengsp/flask-session
    # config values aren't typically objects...
    SESSION_REDIS = redis.from_url(SESSION_REDIS_URL)

    UPDATE_PATIENT_TASK_BATCH_SIZE = 16
    USER_APP_NAME = 'TrueNTH'  # used by email templates
    USER_AFTER_LOGIN_ENDPOINT = 'auth.next_after_login'
    USER_AFTER_CONFIRM_ENDPOINT = USER_AFTER_LOGIN_ENDPOINT
    USER_ENABLE_USERNAME = False  # using email as username
    USER_ENABLE_CHANGE_USERNAME = False  # prereq for disabling username
    USER_ENABLE_CONFIRM_EMAIL = False  # don't force email conf on new accounts
    USER_SHOW_USERNAME_EMAIL_DOES_NOT_EXIST = False

    STAFF_BULK_DATA_ACCESS = True
    PATIENT_LIST_ADDL_FIELDS = []  # 'status', 'reports'
    COPYRIGHT_YEAR = 2018  # TrueNTH copyright year

    FACEBOOK_OAUTH_CLIENT_ID = os.environ.get('FACEBOOK_OAUTH_CLIENT_ID')
    FACEBOOK_OAUTH_CLIENT_SECRET = os.environ.get('FACEBOOK_OAUTH_CLIENT_SECRET')
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')

    DEFAULT_LOCALE = 'en_US'
    FILE_UPLOAD_DIR = 'uploads'

    LR_ORIGIN = os.environ.get('LR_ORIGIN', 'https://stg-lr7.us.truenth.org')
    LR_GROUP = os.environ.get('LR_GROUP', 20145)
    LR_FOLDER_ST = os.environ.get('LR_FOLDER_ST', 35564)

    SYSTEM_TYPE = os.environ.get('SYSTEM_TYPE', 'development')

    # Only set cookies over "secure" channels (HTTPS) for non-dev deployments
    SESSION_COOKIE_SECURE = SYSTEM_TYPE.lower() != 'development'
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'http')

    BABEL_CONFIG_FILENAME = 'gil.babel.cfg'

    SMARTLING_USER_ID = os.environ.get('SMARTLING_USER_ID')
    SMARTLING_USER_SECRET = os.environ.get('SMARTLING_USER_SECRET')
    SMARTLING_PROJECT_ID = os.environ.get('SMARTLING_PROJECT_ID')

    RECAPTCHA_ENABLED = True
    RECAPTCHA_SITE_KEY = os.environ.get('RECAPTCHA_SITE_KEY')
    RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY')
    SECRET_KEY = os.environ.get('SECRET_KEY')

    TREATMENT_OPTIONS = [
        ('373818007', 'http://snomed.info/sct'),
        ('424313000', 'http://snomed.info/sct'),
        ('26294005', 'http://snomed.info/sct'),
        ('26294005-nns', 'http://snomed.info/sct'),
        ('33195004', 'http://snomed.info/sct'),
        ('228748004', 'http://snomed.info/sct'),
        ('707266006', 'http://snomed.info/sct'),
        ('999999999', 'http://snomed.info/sct')]

    LOCKOUT_PERIOD_MINUTES = 30
    FAILED_LOGIN_ATTEMPTS_BEFORE_LOCKOUT = 5

    RESTRICTED_FROM_PROMOTION_ROLES = [
        ROLE.ADMIN.value,
        ROLE.APPLICATION_DEVELOPER.value,
        ROLE.CONTENT_MANAGER.value,
        ROLE.INTERVENTION_STAFF.value,
        ROLE.STAFF.value,
        ROLE.STAFF_ADMIN.value,
        ROLE.SERVICE.value,
    ]


class DefaultConfig(BaseConfig):
    """Default configuration"""
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
    SQLALCHEMY_ECHO = False


class TestConfig(BaseConfig):
    """Testing configuration - used by unit tests"""
    TESTING = True
    MAIL_SUPPRESS_SEND = os.environ.get(
        'MAIL_SUPPRESS_SEND', str(TESTING)).lower() == 'true'
    SERVER_NAME = 'localhost:5005'
    LIVESERVER_PORT = 5005
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = testing_sql_url()

    WTF_CSRF_ENABLED = False
    FILE_UPLOAD_DIR = 'test_uploads'
    SECRET_KEY = 'testing key'
