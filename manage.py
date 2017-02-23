""" Defines a series of scripts for running server and maintenance

python manage.py --help

"""
import os

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

migrate = Migrate(
    app,
    db,
    directory=os.path.join(app.root_path, 'migrations')
)
manager.add_command('db', MigrateCommand)
manager.add_command('runserver', ConfigServer(host='0.0.0.0', threaded=True))


@manager.command
def initdb():
    """Init/reset database."""
    db.drop_all()
    db.create_all()
    seed()


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
