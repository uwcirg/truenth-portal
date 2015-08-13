"""Poral module"""
import logging
from flask import Flask

from .config import DefaultConfig
from .extensions import db, oauth
from .views.api import api
from .views.auth import auth
from .views.portal import portal

logger = logging.getLogger('authomatic.core')
logger.addHandler(logging.StreamHandler())

DEFAULT_BLUEPRINTS = (api, auth, portal)


def create_app(config=None, app_name=None, blueprints=None):
    """Returns the configured flask app"""
    if app_name is None:
        app_name = DefaultConfig.PROJECT
    if blueprints is None:
        blueprints = DEFAULT_BLUEPRINTS

    app = Flask(app_name, template_folder='templates')
    configure_app(app, config)
    configure_extensions(app)
    configure_blueprints(app, blueprints=DEFAULT_BLUEPRINTS)
    return app


def configure_app(app, config):
    """Load successive configs - overriding defaults"""
    app.config.from_object(DefaultConfig)
    app.config.from_pyfile('application.cfg', silent=False)
    if config:
        app.config.from_object(config)


def configure_extensions(app):
    """Bind extensions to application"""
    # flask-sqlalchemy - the ORM / DB used
    db.init_app(app)

    # flask-oauthlib - OAuth between Portal and Interventions
    oauth.init_app(app)


def configure_blueprints(app, blueprints):
    """Register blueprints with application"""
    for blueprint in blueprints:
        app.register_blueprint(blueprint)
