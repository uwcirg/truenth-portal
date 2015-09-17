""" Defines a series of scripts for running server and maintenance

python manage.py --help

"""
from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand

from portal.app import create_app
from portal.extensions import db, ConfigServer
from portal.models.user import User, Role, UserRoles

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


@manager.command
def seed():
    """Seed database with required data"""
    db.session.add(Role(name='patient'))
    db.session.add(Role(name='admin'))
    db.session.commit()

    admin = db.session.query(Role.id).filter(Role.name=='admin').first()
    patient = db.session.query(Role.id).filter(Role.name=='patient').first()

    for u in User.query.all():
        if u.email == 'bob25mary@gmail.com':
            db.session.add(UserRoles(user_id=u.id, role_id=admin))
        db.session.add(UserRoles(user_id=u.id, role_id=patient))
    db.session.commit()


if __name__ == '__main__':
    manager.run()
