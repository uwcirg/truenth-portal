"""Configuration"""
import os


class BaseConfig(object):
    """Base configuration - override in subclasses"""
    PROJECT = "portal"
    PROJECT_ROOT =\
            os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    DEBUG = False
    LOG_FOLDER = os.path.join('/var/log', __package__)
    LOG_LEVEL = 'DEBUG'
    TESTING = False
    SECRET_KEY = 'override this secret key'
    USER_UNAUTHORIZED_ENDPOINT = 'portal.index'
    USER_UNAUTHENTICATED_ENDPOINT = 'portal.index'


class DefaultConfig(BaseConfig):
    """Default configuration"""
    DEBUG = True
    SQLALCHEMY_ECHO = False


class TestConfig(BaseConfig):
    """Testing configuration - used by unit tests"""
    TESTING = True
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = 'sqlite://'


from flask import Config
def early_app_config_access():
    """Workaround to bootstrap configuration problems

    Some extensions require config values before the flask app can be
    initialized.  Expose the same configuration used by the app by
    direct access.

    Avoid use of this approach, as the app has its own config with a
    chain of overwrites.  i.e. use app.config whenever possible.

    """
    _app_config = Config(None)
    _app_config.from_pyfile(os.path.join(\
            os.path.dirname(__file__), 'application.cfg'))
    return _app_config
