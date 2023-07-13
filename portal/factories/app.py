"""Portal module"""

import email.parser
import json_logging
import logging
from logging import handlers
import os
import sys

from flask import Flask
from healthcheck import HealthCheck
from pkg_resources import get_distribution
import redis
import requests_cache
from werkzeug.middleware.profiler import ProfilerMiddleware

# Hack - workaround to cyclic imports/missing SQLA models for docker
from ..audit import configure_audit_log
from ..cache import cache
from ..config.config import SITE_CFG, DefaultConfig, TestConfig
from ..config.site_persistence import SitePersistence
from ..csrf import csrf, csrf_blueprint
from ..database import db
from ..extensions import babel, mail, oauth, recaptcha, session, user_manager
from ..models.app_text import app_text
from ..models.coredata import configure_coredata
from ..models.intervention import INTERVENTION
from ..models.role import ROLE
from ..views.assessment_engine import assessment_engine_api
from ..views.audit import audit_api
from ..views.auth import (
    auth,
    capture_next_view_function,
    facebook_blueprint,
    google_blueprint,
)
from ..views.client import client_api
from ..views.clinical import clinical_api
from ..views.clinician import clinician_api
from ..views.coredata import coredata_api
from ..views.demographics import demographics_api
from ..views.extend_flask_user import (
    LockoutLoginForm,
    reset_password_view_function,
)
from ..views.external_assets import asset_api
from ..views.fhir import fhir_api
from ..views.filters import filters_blueprint
from ..views.group import group_api
from ..views.healthcheck import (
    HEALTH_CHECKS,
    HEALTHCHECK_FAILURE_STATUS_CODE,
    healthcheck_blueprint,
)
from ..views.identifier import identifier_api
from ..views.intervention import intervention_api
from ..views.notification import notification_api
from ..views.organization import org_api
from ..views.patient import patient_api
from ..views.patients import patients
from ..views.portal import portal
from ..views.practitioner import practitioner_api
from ..views.procedure import procedure_api
from ..views.questionnaire import questionnaire_api
from ..views.reporting import reporting_api
from ..views.research_study import research_study_api
from ..views.role import role_api
from ..views.scheduled_job import scheduled_job_api
from ..views.staff import staff
from ..views.tou import tou_api
from ..views.truenth import truenth_api
from ..views.user import user_api

DEFAULT_BLUEPRINTS = (
    assessment_engine_api,
    asset_api,
    audit_api,
    auth,
    client_api,
    coredata_api,
    clinical_api,
    clinician_api,
    csrf_blueprint,
    demographics_api,
    facebook_blueprint,
    fhir_api,
    filters_blueprint,
    google_blueprint,
    group_api,
    healthcheck_blueprint,
    identifier_api,
    intervention_api,
    notification_api,
    org_api,
    patient_api,
    patients,
    practitioner_api,
    procedure_api,
    portal,
    questionnaire_api,
    reporting_api,
    research_study_api,
    role_api,
    scheduled_job_api,
    staff,
    truenth_api,
    tou_api,
    user_api,
)


def create_app(config=None, app_name=None, blueprints=None):
    """Returns the configured flask app"""
    if app_name is None:
        app_name = DefaultConfig.PROJECT
    if blueprints is None:
        blueprints = DEFAULT_BLUEPRINTS

    app = Flask(app_name, template_folder='templates',
                instance_relative_config=True)
    configure_app(app, config)
    configure_profiler(app)
    configure_csrf(app)
    configure_jinja(app)
    configure_extensions(app)
    configure_blueprints(app, blueprints=DEFAULT_BLUEPRINTS)
    configure_logging(app)
    configure_audit_log(app)
    configure_metadata(app)
    configure_coredata(app)
    configure_cache(app)
    configure_healthcheck(app)
    return app


def configure_app(app, config):
    """Load successive configs - overriding defaults"""
    app.config.from_object(DefaultConfig)
    app.config.from_pyfile('base.cfg', silent=True)
    site_cfg_fullpath = os.path.join(app.config.root_path, SITE_CFG)
    if not os.path.isfile(site_cfg_fullpath):
        app.logger.warn(f"{site_cfg_fullpath} not found!!!!!!!!!!!!!")
    else:
        app.logger.warn(f"{site_cfg_fullpath} FOUND!!!!!!!!!!!!!!")
    app.config.from_pyfile(SITE_CFG, silent=True)
    app.config.from_pyfile('application.cfg', silent=True)

    if config:
        app.config.from_object(config)
    elif os.environ.get('TESTING', 'false').lower() == 'true':
        app.config.from_object(TestConfig)

    # Set email "from" addresss if not set yet
    if 'MAIL_DEFAULT_SENDER' not in app.config:
        app.config['MAIL_DEFAULT_SENDER'] = '"TrueNTH" <noreply@{}>'.format(
            app.config['SERVER_NAME'].split(':')[0]
        )


def configure_profiler(app):
    if app.config.get('PROFILE'):
        app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])


def configure_csrf(app):
    """Initialize CSRF protection

    See `csrf.csrf_protect()` for implementation.  Not using default
    as OAuth API use needs exclusion.

    """
    csrf.init_app(app)


def configure_jinja(app):
    app.jinja_env.globals.update(app_text=app_text)
    app.jinja_env.globals.update(ROLE=ROLE)
    app.jinja_env.globals.update(INTERVENTION=INTERVENTION)
    app.jinja_env.globals.update(WTF_CSRF_TIME_LIMIT=app.config.get("WTF_CSRF_TIME_LIMIT"))


def configure_extensions(app):
    """Bind extensions to application"""
    # flask-sqlalchemy - the ORM / DB used
    db.init_app(app)
    if app.testing:
        session_options = {}
        db.session_options = session_options

    # flask-user

    # The default login and register view functions fail to capture
    # the next parameter in a reliable fashion.  Using a simple closure
    # capture 'next' before redirecting to the real view function to
    # manage the flask-user business logic

    from flask_user.views import login, register
    from ..views.patch_flask_user import (
        patch_make_safe_url, patch_forgot_password, patch_send_email)

    user_manager.init_app(
        app,
        forgot_password_view_function=patch_forgot_password,
        login_form=LockoutLoginForm,
        send_email_function=patch_send_email,
        make_safe_url_function=patch_make_safe_url,
        reset_password_view_function=reset_password_view_function,
        register_view_function=capture_next_view_function(register),
        login_view_function=capture_next_view_function(login))

    # flask-oauthlib - OAuth between Portal and Interventions
    oauth.init_app(app)

    # flask-mail - Email communication
    mail.init_app(app)

    # flask-session - Server side sessions
    session.init_app(app)

    # babel - i18n
    babel.init_app(app)

    # recaptcha - form verification
    recaptcha.init_app(app)


def configure_blueprints(app, blueprints):
    """Register blueprints with application"""
    # Load GIL or ePROMs blueprint (which define several of the same request
    # paths and would therefore conflict with one another) depending on config
    if app.config.get('GIL') and not app.config.get('HIDE_GIL'):
        from ..gil.views import gil
        from ..exercise_diet.views import exercise_diet
        app.register_blueprint(gil)
        app.register_blueprint(exercise_diet)
    else:
        from ..eproms.views import eproms
        from ..trigger_states.views import trigger_states
        app.register_blueprint(eproms)
        app.register_blueprint(trigger_states)

    for blueprint in blueprints:
        app.register_blueprint(blueprint)


def configure_logging(app):  # pragma: no cover
    """Configure logging."""
    # Avoid duplicate logging.  Multiple handlers implies logging
    # has already been configured
    if len(app.logger.handlers) > 1:
        return

    # Configure for JSON logging
    if json_logging._current_framework is None:
        # Ugly internal ref to prevent multiple calls to `init_flask`
        json_logging.init_flask(enable_json=True)
        json_logging.init_request_instrument(app)

    if app.config.get('LOG_SQL'):
        import portal.sql_logging

    level = getattr(logging, app.config['LOG_LEVEL'].upper())
    from ..tasks import logger as task_logger
    task_logger.setLevel(level)
    app.logger.setLevel(level)

    if app.testing or not app.config.get('LOG_FOLDER'):
        # Write logs to stdout by default and when testing
        return

    # Configure Error Emails for high level log messages, only in prod mode
    if not os.path.exists(app.config['LOG_FOLDER']):
        os.mkdir(app.config['LOG_FOLDER'])

    info_log = os.path.join(app.config['LOG_FOLDER'], 'info.log')
    # For WSGI servers, the log file is only writable by www-data
    # This prevents users from being able to run other management
    # commands as themselves.  If current user can't write to the
    # info_log, bail out - relying on stdout/stderr
    try:
        with open(info_log, 'a+'):
            pass
    except IOError:
        print(
            "Can't open log file '%s', use stdout" % info_log,
            "Set LOG_FOLDER to a writable directory in configuration file",
            file=sys.stderr,
        )
        return

    info_file_handler = handlers.RotatingFileHandler(
        info_log, maxBytes=1000000, backupCount=20)
    info_file_handler.setLevel(level)
    info_file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]')
    )

    app.logger.addHandler(info_file_handler)
    task_logger.addHandler(info_file_handler)

    # OAuth library logging tends to be helpful for connection
    # debugging
    for logger in ('oauthlib', 'flask_oauthlib'):
        log = logging.getLogger(logger)
        log.setLevel(level)
        log.addHandler(info_file_handler)

    # app.logger.debug("initiate logging done at level %s, %d",
    #    app.config['LOG_LEVEL'], level)


def configure_metadata(app):
    """Add distribution metadata for display in templates"""
    distribution = get_distribution('portal')
    metadata_str = distribution.get_metadata(distribution.PKG_INFO)
    metadata = email.parser.Parser().parsestr(metadata_str)

    # Get git hash from version if present
    # https://github.com/pypa/setuptools_scm#default-versioning-scheme
    # Todo: extend Distribution base class instead of monkey patching
    version = metadata.get('version')
    if version and '+' in version:
        metadata['git_hash'] = version.split('+')[-1].split('.')[0][1:]

    app.config.metadata = metadata


def configure_cache(app):
    """Configure caching libraries"""
    # flask-cache
    cache.init_app(app)

    # requests-cache
    REQUEST_CACHE_URL = app.config.get("REQUEST_CACHE_URL")

    requests_cache.install_cache(
        cache_name=app.name,
        backend='redis',
        expire_after=app.config['REQUEST_CACHE_EXPIRE'],
        include_get_headers=True,
        old_data_on_error=True,
        connection=redis.StrictRedis.from_url(REQUEST_CACHE_URL),
    )


def configure_healthcheck(app):
    """Configure the API used to check the health of our dependencies"""
    # Initializes the /healthcheck API that returns
    # the health of the service's dependencies based
    # on the results of the given checks
    app.healthcheck = HealthCheck(
        app=app,
        path='/healthcheck',
        checkers=HEALTH_CHECKS,
        failed_status=HEALTHCHECK_FAILURE_STATUS_CODE,
        log_on_failure=False,
    )
