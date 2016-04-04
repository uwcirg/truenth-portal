"""Poral module"""
from logging import handlers
import logging
import os
import sys
from flask import Flask
from flask.ext.webtest import get_scopefunc

from .audit import configure_audit_log
from .config import DefaultConfig
from .extensions import babel, celery, db, mail, oauth, user_manager
from .views.api import api
from .views.auth import auth
from .views.portal import portal, page_not_found, server_error


DEFAULT_BLUEPRINTS = (api, auth, portal)


def create_app(config=None, app_name=None, blueprints=None):
    """Returns the configured flask app"""
    if app_name is None:
        app_name = DefaultConfig.PROJECT
    if blueprints is None:
        blueprints = DEFAULT_BLUEPRINTS

    app = Flask(app_name, template_folder='templates')
    configure_app(app, config)
    configure_error_handlers(app)
    configure_extensions(app)
    configure_blueprints(app, blueprints=DEFAULT_BLUEPRINTS)
    configure_logging(app)
    configure_audit_log(app)
    configure_version(app)
    return app


def configure_app(app, config):
    """Load successive configs - overriding defaults"""
    app.config.from_object(DefaultConfig)
    app.config.from_pyfile('application.cfg', silent=False)
    if config:
        app.config.from_object(config)


def configure_error_handlers(app):
    app.register_error_handler(404, page_not_found)
    app.register_error_handler(500, server_error)


def configure_extensions(app):
    """Bind extensions to application"""
    # flask-sqlalchemy - the ORM / DB used
    db.init_app(app)
    if app.testing:
        session_options = {}
        session_options['scopefunc'] = get_scopefunc()
        db.session_options = session_options

    # flask-user
    user_manager.init_app(app)

    # flask-oauthlib - OAuth between Portal and Interventions
    oauth.init_app(app)

    # flask-mail - Email communication
    mail.init_app(app)

    # celery - task queue for asynchronous tasks
    celery.init_app(app)

    # babel - i18n
    babel.init_app(app)


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
        print >> sys.stderr,\
            "Set LOG_FOLDER to a writable directory in configuration file"
        return

    info_file_handler = handlers.RotatingFileHandler(info_log,
            maxBytes=1000000, backupCount=20)
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

    from .tasks import logger
    logger.setLevel(level)
    logger.addHandler(info_file_handler)

    # Configure Error Emails for high level log messages, only in prod mode
    ADMINS = app.config['ERROR_SENDTO_EMAIL']
    if not app.debug:
        mail_handler = handlers.SMTPHandler(
            '127.0.0.1',
            app.config['MAIL_DEFAULT_SENDER'],
            ADMINS,
            '{} Log Message'.format(app.config['SERVER_NAME']))
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)

    #app.logger.debug("initiate logging done at level %s, %d",
    #    app.config['LOG_LEVEL'], level)


def configure_version(app):
    """Add version info for display in templates"""
    location = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(location, 'VERSION'), 'r') as version:
        app.config.version = version.readline()
