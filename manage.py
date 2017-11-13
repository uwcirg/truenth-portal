""" Defines a series of scripts for running server and maintenance

FLASK_APP=manage.py flask --help

"""
import os
import click
import redis

import alembic.config
from flask_migrate import Migrate

from portal.factories.app import create_app
from portal.extensions import db
from portal.models.i18n import smartling_upload, smartling_download
from portal.models.fhir import add_static_concepts
from portal.models.intervention import add_static_interventions
from portal.models.organization import add_static_organization
from portal.models.relationship import add_static_relationships
from portal.models.role import add_static_roles
from portal.models.user import permanently_delete_user, flag_test
from portal.models.user_consent import db_maintenance
from config.site_persistence import SitePersistence

app = create_app()

MIGRATIONS_DIR = os.path.join(app.root_path, 'migrations')
migrate = Migrate(app, db, directory=MIGRATIONS_DIR)

@app.cli.command()
def runserver():
    # Todo: figure out how to override default host in `flask run`
    # http://click.pocoo.org/5/commands/#overriding-defaults
    app.run(
        host='0.0.0.0',
        threaded=True,
        use_debugger=True,
        use_reloader=True,
    )


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
    """Flush redis of all values. Cached values may not longer correspond with new DB entries"""
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


@click.option('--exclude_interventions', '-e', default=False,
              help="Exclude (don't overwrite) intervention data")
@click.option('--keep_unmentioned', '-k', default=False, help='Keep orgs and interventions not mentioned in persistence file')
@app.cli.command(name="seed")
def seed_command(exclude_interventions, keep_unmentioned):
    seed(exclude_interventions, keep_unmentioned)

def seed(exclude_interventions=False, keep_unmentioned=False):
    """Seed database with required data"""

    # Request context necessary for generating data from own HTTP APIs
    with app.test_request_context():
        add_static_concepts()

    add_static_interventions()
    add_static_organization()
    add_static_relationships()
    add_static_roles()
    db_maintenance()
    db.session.commit()

    # Always update interventions on development systems
    if app.config["SYSTEM_TYPE"].lower() == 'development':
        exclude_interventions = False

    # import site export file if found
    SitePersistence().import_(exclude_interventions, keep_unmentioned)


@app.cli.command()
def export_site():
    """Generate JSON file containing dynamic site config

    Portions of site configuration live in the database, such as
    Organizations and Access Strategies.  Generate a single export
    file for migration of this data to other instances of the service.

    NB the seed command imports the data file if found, along with
    other static data.

    """
    SitePersistence().export()


@click.option('--email', '-e', help='Email of user to purge.')
@click.option(
    '--actor', '-a',
    help='Email of user to act as.',
    prompt= \
        "\n\nWARNING!!!\n\n"
        " This will permanently delete the target user and all their related data.\n"
        " If you want to contiue,"
        " enter a valid user email as the acting party for our records"
)
@app.cli.command()
def purge_user(email, actor):
    """Purge the given user from the system"""
    # import ipdb; ipdb.set_trace()
    permanently_delete_user(email, actor=actor)


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
@app.cli.command()
def translation_download(language):
    """Download .po file(s) from Smartling

    GETs the .po file for the specified language from Smartling via their API.
    If no language is specified, all available translations will be downloaded.
    After download, .po file(s) are compiled into .mo file(s) using pybabel
    """
    smartling_download(language)
