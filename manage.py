""" Defines a series of scripts for running server and maintenance

python manage.py --help

"""
import os

import alembic.config
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand

from portal.app import create_app
from portal.config import ConfigServer
from portal.extensions import db
from portal.models.i18n import upsert_to_template_file
from portal.models.fhir import add_static_concepts
from portal.models.intervention import add_static_interventions
from portal.models.organization import add_static_organization
from portal.models.relationship import add_static_relationships
from portal.models.role import add_static_roles
from portal.models.user import permanently_delete_user, flag_test
from portal.models.user_consent import db_maintenance
from portal.site_persistence import SitePersistence

app = create_app()
manager = Manager(app)

MIGRATIONS_DIR = os.path.join(app.root_path, 'migrations')
migrate = Migrate(app, db, directory=MIGRATIONS_DIR)
manager.add_command('db', MigrateCommand)
manager.add_command('runserver', ConfigServer(host='0.0.0.0', threaded=True))


def stamp_db():
    """Run the alembic command to stamp the db with the current head"""
    # if the alembic_version table exists, this db has been stamped,
    # don't update to head, as it would potentially skip steps.
    if db.engine.dialect.has_table(db.engine.connect(), 'alembic_version'):
        return

    alembic_args = [
        '--raiseerr',
        'stamp',
        'head']
    # Alembic looks for the alembic.ini file in CWD
    # hop over there and then return to CWD
    cwd = os.getcwd()
    os.chdir(MIGRATIONS_DIR)
    alembic.config.main(argv=alembic_args)
    os.chdir(cwd)


@manager.command
def initdb():
    """Init database.

    To re/create the database, [delete and] create within the DBMS itself,
    then invoke this function.
    """
    db.create_all()
    # Stamp the current alembic version, so subesquent upgrades know
    # the correct starting point
    stamp_db()
    seed(include_interventions=True)


@manager.command
def seed(include_interventions=False, keep_unmentioned=False):
    """Seed database with required data"""
    add_static_concepts()
    add_static_interventions()
    add_static_organization()
    add_static_relationships()
    add_static_roles()
    db_maintenance()
    db.session.commit()

    # Always update interventions on development systems
    if app.config["SYSTEM_TYPE"].lower() == 'development':
        include_interventions = True

    # import site export file if found
    SitePersistence().import_(include_interventions, keep_unmentioned)


@manager.command
def export_site():
    """Generate JSON file containing dynamic site config

    Portions of site configuration live in the database, such as
    Organizations and Access Strategies.  Generate a single export
    file for migration of this data to other instances of the service.

    NB the seed command imports the data file if found, along with
    other static data.

    """
    SitePersistence().export()


@manager.option('-u', '--username', dest='username')
def purge_user(username):
    """Purge the given user from the system"""
    permanently_delete_user(username)


@manager.command
def mark_test():
    """Designate all current users as test users"""
    flag_test()


@manager.command
def translations():
    """Add extracted DB strings to existing PO template file"""
    upsert_to_template_file()


if __name__ == '__main__':
    manager.run()
