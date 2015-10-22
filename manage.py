""" Defines a series of scripts for running server and maintenance

python manage.py --help

"""
from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand

from portal.app import create_app
from portal.extensions import db, ConfigServer
from portal.models.auth import Client
from portal.models.user import User, Role, UserRoles, add_static_data

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
    add_static_data(db)


@manager.command
def seed():
    """Seed database with required data"""
    app_dev = db.session.query(Role.id).\
            filter(Role.name=='application_developer').first()
    if not app_dev:
        db.session.add(Role(name='application_developer'))
        db.session.commit()
        app_dev = db.session.query(Role.id).\
                filter(Role.name=='application_developer').first()

    u_r = {}
    for c in Client.query.all():
        existing = UserRoles.query.filter_by(user_id=c.user_id,
                role_id=app_dev).first()
        if not existing:
            u_r[c.user_id] = app_dev

    for u, r in u_r.items():
        db.session.add(UserRoles(user_id=u, role_id=r))
    db.session.commit()


if __name__ == '__main__':
    manager.run()
