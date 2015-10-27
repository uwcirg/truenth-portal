""" Defines a series of scripts for running server and maintenance

python manage.py --help

"""
from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand

from portal.app import create_app
from portal.config import ConfigServer
from portal.extensions import db
from portal.models.auth import Client
from portal.models.user import User, UserRoles
from portal.models.role import Role, add_static_data

app = create_app()
manager = Manager(app)

migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)
manager.add_command('runserver', ConfigServer(host='0.0.0.0'))


@manager.command
def initdb():
    """Init/reset database."""
    db.drop_all()
    db.create_all()
    add_static_data()


@manager.command
def seed():
    """Seed database with required data"""
    add_static_data()


if __name__ == '__main__':
    manager.run()
