"""Poral module"""
from logging import handlers
import logging
import os
import sys
from flask import Flask

from .config import DefaultConfig
from .extensions import db, oauth, user_manager
from .views.api import api
from .views.auth import auth
from .views.portal import portal


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
    configure_logging(app)
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

    # flask-user
    user_manager.init_app(app)

    # flask-oauthlib - OAuth between Portal and Interventions
    oauth.init_app(app)


def configure_blueprints(app, blueprints):
    """Register blueprints with application"""
    for blueprint in blueprints:
        app.register_blueprint(blueprint)


def configure_logging(app):
    """Configure logging."""
    if app.testing:
        # Skip test mode. Just check standard output.
        return

    if not os.path.exists(app.config['LOG_FOLDER']):
        os.mkdir(app.config['LOG_FOLDER'])

    level = getattr(logging, app.config['LOG_LEVEL'].upper())

    info_log = os.path.join(app.config['LOG_FOLDER'], 'info.log')
    # For WSGI servers, the log file is only writable by www-data
    # This prevents users from being able to run other management
    # commands as themselves.  If current user can't write to the
    # info_log, bail out - relying on stdout/stderr
    try:
        with open(info_log, 'a+'):
            pass
    except IOError:
        print >> sys.stderr, "Can't open log file '%s', use stdout" %\
            info_log
        return

    info_file_handler = handlers.RotatingFileHandler(info_log,
            maxBytes=100000, backupCount=10)
    info_file_handler.setLevel(level)
    info_file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]')
    )

    app.logger.setLevel(level)
    app.logger.addHandler(info_file_handler)

    # OAuth library logging tends to be helpful for connection
    # debugging
    for logger in ('oauthlib', 'flask_oauthlib', 'authomatic.core'):
        log = logging.getLogger(logger)
        log.setLevel(level)
        log.addHandler(info_file_handler)

    #app.logger.debug("initiate logging done at level %s, %d",
    #    app.config['LOG_LEVEL'], level)
