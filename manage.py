""" Defines a series of scripts for running server and maintenance

python manage.py --help

"""
from flask.ext.script import Manager, Server
from flask.ext.migrate import Migrate, MigrateCommand

from portal.app import create_app
from portal.extensions import db

app = create_app()
manager = Manager(app)

migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)
manager.add_command('runserver', Server(host='0.0.0.0'))


@manager.command
def initdb():
    """Init/reset database."""

    db.drop_all()
    db.create_all()


if __name__ == '__main__':
    manager.run()
