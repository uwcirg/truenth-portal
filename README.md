# true_nth_usa_portal_demo
Demo for the Movember True NTH USA portal - early summer 2015

## INSTALLATION

Pull down prerequisite packages

```bash
$ sudo apt-get install python-virtualenv
```

From the parent directory where you wish to install the portal, pull
down the code and create a virtual environment to isolate the 
requirements from the system python

```bash
$ git clone https://github.com/uwcirg/true_nth_usa_portal_demo.git portal
$ virtualenv portal
$ cd portal
```

Activate the virtual environment, patch setuptools, and install the
project requirements (into the virtual environment)

```bash
$ source bin/activate
$ pip install -U setuptools
```

To install for development (so changes to source files don't require
another round of install, use the develop flag

```bash
$ python setup.py develop
```

To install on a server, use the install flag

```bash
$ python setup.py install
```

## CONFIGURE

Copy the default to the named configuration file

```bash
$ cp portal/application.cfg.default portal/application.cfg
```

Obtain `consumer_key` and `consumer_secret` values from https://developers.facebook.com/apps  Write the values from Facebook to `application.cfg`:

```bash
# application.cfg
[...]
CONSUMER_KEY = '<App ID From FB>'
CONSUMER_SECRET = '<App Secret From FB>'
```

## RUN
```bash
$ python manage.py runserver
```

## DATABASE

The value of `SQLALCHEMY_DATABASE_URI` defines which database engine
and database to use.  In general, sqlite is used for small testing
instances, and PostgreSQL is used otherwise.

### Migrations

Thanks to Alembic and Flask-Migrate, database migrations are easily
managed and run.  Update the python source files containing table
definitions (typically classes derrived from db.Model) and run the
manage script to generate the necessary migration code:

```bash
cd PROJECT_HOME
source bin/activate
python manage.py db migrate
```

Then execute the upgrade on any database (edit `SQLALCHEMY_DATABASE_URI`
in the `application.cfg` file to alter database target):

```bash
python manage.py db upgrade
```

## Testing

All test modules under the `tests` directory can be executed via `nosetests`
(again from project root with the virtual environment activated)

```bash
$ nosetests
```
