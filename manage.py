""" Defines a series of scripts for running server and maintenance

FLASK_APP=manage.py flask --help

"""
import json
import os

import alembic.config
import click
from flask import url_for
from flask_migrate import Migrate
from past.builtins import basestring
import redis
import requests
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound
import sys

from portal.audit import auditable_event
from portal.config.site_persistence import SitePersistence
from portal.extensions import db, user_manager
from portal.factories.app import create_app
from portal.models.clinical_constants import add_static_concepts
from portal.models.i18n import smartling_download, smartling_upload
from portal.models.i18n_utils import download_all_translations
from portal.models.intervention import add_static_interventions
from portal.models.organization import add_static_organization
from portal.models.relationship import add_static_relationships
from portal.models.role import ROLE, Role, add_static_roles
from portal.models.user import (
    User,
    flag_test,
    permanently_delete_user,
    validate_email,
)
from portal.models.url_token import (
    BadSignature,
    SignatureExpired,
    verify_token,
)
from portal.tasks import celery_beat_health_check

app = create_app()

MIGRATIONS_DIR = os.path.join(app.root_path, 'migrations')
migrate = Migrate(app, db, directory=MIGRATIONS_DIR)


def _run_alembic_command(args):
    """Helper to manage working directory and run given alembic commands"""
    # Alembic looks for the alembic.ini file in CWD
    # hop over there and then return to CWD
    cwd = os.getcwd()
    os.chdir(MIGRATIONS_DIR)

    alembic.config.main(argv=args)

    os.chdir(cwd)  # restore cwd


def stamp_db():
    """Run the alembic command to stamp the db with the current head"""
    # if the alembic_version table exists, this db has been stamped,
    # don't update to head, as it would potentially skip steps.
    if db.engine.dialect.has_table(db.engine.connect(), 'alembic_version'):
        return

    _run_alembic_command(['--raiseerr', 'stamp', 'head'])


def upgrade_db():
    """Run any outstanding migration scripts"""
    _run_alembic_command(['--raiseerr', 'upgrade', 'head'])


def flush_cache():
    """Flush redis of all values.

    Cached values may no longer correspond with new DB entries.
    NB this may incur a significant performance hit as all cached
    entries will be invalidated.

    """
    if app.config.get('FLUSH_CACHE_ON_SYNC'):
        r = redis.from_url(app.config['REDIS_URL'])
        r.flushdb()


@app.cli.command()
def sync():
    """Synchronize database with latest schema and persistence data.

    Idempotent function takes necessary steps to build tables, migrate
    schema and run `seed`.  Safe to run on existing or brand new databases.

    To re/create the database, [delete and] create within the DBMS itself,
    then invoke this function.
    """
    if not db.engine.dialect.has_table(db.engine.connect(), 'alembic_version'):
        db.create_all()
    stamp_db()
    flush_cache()
    upgrade_db()
    seed()


@click.option(
    '--keep_unmentioned', '-k', default=False,
    help='Keep orgs and interventions not mentioned in persistence file')
@app.cli.command(name="seed")
def seed_command(keep_unmentioned):
    """Seed database with required data"""
    seed(keep_unmentioned)


def seed(keep_unmentioned=False):
    """Actual seed function

    NB this is defined separately so it can also be called internally,
    i.e. from sync

    """
    # Request context necessary for generating data from own HTTP APIs
    with app.test_request_context():
        add_static_concepts()

    add_static_interventions()
    add_static_organization()
    add_static_relationships()
    add_static_roles()
    db.session.commit()

    # import site export file if found
    SitePersistence(target_dir=None).import_(
        keep_unmentioned=keep_unmentioned)


@click.option('--directory', '-d', default=None, help="Export directory")
@click.option(
    '--staging_exclusion', '-x', default=False, is_flag=True,
    help="Staging Exclusions Export")
@app.cli.command()
def export_site(directory, staging_exclusion):
    """Generate JSON file containing dynamic site config

    :param directory: used to name a non-default target directory for export
      files
    :param staging_exclusion: set only if persisting exclusions to retain
      on staging when pulling over production data.

    Portions of site configuration live in the database, such as
    Organizations and Access Strategies.  Generate a single export
    file for migration of this data to other instances of the service.

    NB the seed command imports the data file if found, along with
    other static data.

    """
    if staging_exclusion and not directory:
        directory = app.config.get("PERSISTENCE_EXCLUSIONS_DIR")

    SitePersistence(target_dir=directory).export(
        staging_exclusion=staging_exclusion)


@click.option('--directory', '-d', default=None, help="Import directory")
@app.cli.command()
def import_site_exclusions(directory):
    """Import serialized exclusions (saved on stage prior to prod db overwrite)

    :param directory: used to name a non-default target directory for import
      files

    """
    if not directory:
        directory = app.config.get("PERSISTENCE_EXCLUSIONS_DIR")

    SitePersistence(target_dir=directory).import_(
        staging_exclusion=True, keep_unmentioned=True)


@click.option('--email', '-e', help="email address for new user")
@click.option('--role', '-r', help="Comma separated role(s) for new user")
@click.option('--password', '-p', help="password for new user")
@app.cli.command()
def add_user(email, role, password):
    """Add new user as specified """
    validate_email(email)
    if not password or len(str(password)) < 5:
        raise ValueError("requires a password")

    pw = user_manager.hash_password(password)
    user = User(email=email, password=pw)
    db.session.add(user)
    roles = role.split(',') if role else []
    try:
        role_list = [
            Role.query.filter_by(name=r).one() for r in roles]
        user.update_roles(role_list, acting_user=user)
    except NoResultFound:
        raise ValueError(
            "one or more roles ill defined {}".format(roles))

    db.session.commit()
    auditable_event(
        "new account generated (via cli) for {}".format(user),
        user_id=user.id, subject_id=user.id, context='account')


@click.option('--email', '-e', help="target user email for password reset")
@click.option('--password', '-p', help="new password")
@click.option(
    '--actor', '-a',
    help='Email of user taking this action (must be admin)'
)
@app.cli.command()
def password_reset(email, password, actor):
    """Reset given user's password """
    try:
        acting_user = User.query.filter(
            func.lower(User.email) == actor.lower()).one()
    except NoResultFound:
        raise ValueError("email for acting user <{}> not found".format(actor))
    try:
        target_user = User.query.filter(
            func.lower(User.email) == email.lower()).one()
    except NoResultFound:
        raise ValueError("email for target user not found")
    if not acting_user.has_role(ROLE.ADMIN.value):
        raise ValueError("Actor must be an admin")
    if not password or len(str(password)) < 8:
        raise ValueError("requires a valid password")

    target_user.password = user_manager.hash_password(password)
    db.session.commit()
    auditable_event(
        "cli password reset for {}".format(target_user),
        user_id=acting_user.id, subject_id=target_user.id, context='account')


@click.option('--email', '-e', help='Email of user to purge.')
@click.option(
    '--actor', '-a',
    help='Email of user to act as.',
    prompt=(
        "\n\nWARNING!!!\n\n"
        " This will permanently delete the target user and all their related"
        " data.\n"
        " If you want to continue,"
        " enter a valid user email as the acting party for our records")
)
@app.cli.command()
def purge_user(email, actor):
    """Purge the given user from the system"""
    # import ipdb; ipdb.set_trace()
    permanently_delete_user(email, actor=actor)


@click.argument('token')
@app.cli.command()
def token_details(token):
    valid_seconds = app.config.get(
        'TOKEN_LIFE_IN_DAYS') * 24 * 3600
    try:
        user_id = verify_token(token, valid_seconds)
    except SignatureExpired:
        click.echo("EXPIRED token (older than {} seconds)".format(
            valid_seconds))
    except BadSignature:
        click.echo("INVALID token")
    else:
        click.echo("Valid token for user_id {}".format(user_id))


@app.cli.command()
def mark_test():
    """Designate all current users as test users"""
    flag_test()


@app.cli.command()
def translation_upload():
    """Update .pot file on Smartling

    Creates a new .pot file, updates the file with relevant DB entries, then
    POSTs said .pot file to Smartling via their API
    """
    smartling_upload()


@click.option('--language', '-l', help='language code (e.g. en_US).')
@click.option('--state', '-s', help='Translation state', type=click.Choice([
    'pseudo',
    'pending',
    'published',
    'contextMatchingInstrumented',
]))
@app.cli.command()
def translation_download(language, state):
    """Download .po file(s) from Smartling

    GETs the .po file for the specified language from Smartling via their API.
    If no language is specified, all available translations will be downloaded.
    After download, .po file(s) are compiled into .mo file(s) using pybabel
    """

    default_state = 'pending'
    if app.config['SYSTEM_TYPE'].lower() == 'production':
        default_state = 'published'
    state = state or default_state
    click.echo(
        'Downloading {state} translations from Smartling'.format(state=state))
    smartling_download(state=state, language=language)


@click.option('--state', '-s', help='Translation state', type=click.Choice([
    'pseudo',
    'pending',
    'published',
    'contextMatchingInstrumented',
]))
@app.cli.command()
def download_translations(state):
    default_state = 'pending'
    if app.config['SYSTEM_TYPE'].lower() == 'production':
        default_state = 'published'
    state = state or default_state
    click.echo(
        'Downloading {state} translations from every Smartling project'.format(state=state)
    )
    download_all_translations(state=state)


@click.option(
    '--config_key',
    '-c',
    help='Return a single config value, or empty string if value is None'
)
@app.cli.command()
def config(config_key):
    """List current flask configuration values in JSON"""

    if config_key:
        # Remap None values to an empty string
        print(app.config.get(config_key, '') or '')
        return
    print(json.dumps(
        # Skip un-serializable values
        {k: v for k, v in app.config.items() if isinstance(v, basestring)},
        indent=2,
    ))


@app.cli.command()
def set_celery_beat_healthy():
    return celery_beat_health_check()


@app.cli.command()
def healthcheck():
    """Calls the healthcheck API"""
    result = requests.get(
        url_for('check')
    )
    print(json.dumps(result.json(), indent=4))

    # Return success (0) if passing status code
    if result.ok:
        return sys.exit()

    # Healthcheck failed. Return a failing status code
    return sys.exit(result.status_code)
