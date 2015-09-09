# true_nth_usa_portal_demo
Movember True NTH USA Central Services

## INSTALLATION

Pick any path for installation

```bash
$ export PROJECT_HOME=~/CentralServices
```

### Prerequisites (done one time)

#### Install required packages

```bash
$ sudo apt-get install python-virtualenv libffi-dev
```

#### Clone the Project

```bash
$ git clone https://github.com/uwcirg/true_nth_usa_portal_demo.git \
    $PROJECT_HOME
```

#### Create a Virtual Environment

This critical step enables isolation of the project from system python,
making dependency maintenance easier and more stable.  It does require
that you ```activate``` the virtual environment before you interact
with python or the installer scripts.

```bash
$ virtualenv $PROJECT_HOME
```

#### Activate the Virtual Environment

Required to interact with the python installed in this virtual
environment.  Forgetting this step will result in obvious warnings
about missing dependencies.

```bash
$ cd $PROJECT_HOME
$ source bin/activate
```

#### Patch setuptools

A one time workaround to a bootstrap upgrade problem with setuptools:

```bash
$ cd $PROJECT_HOME
$ source bin/activate
$ pip install -U setuptools
```

### Install the Lastest Package

```bash
$ cd $PROJECT_HOME
$ git pull
```

Technically, the following `pip` step only needs to be re-run when the
project requirements change (i.e. new values in setup.py
install_requires), but it's safe to run anytime to make sure.

```bash
$ pip install -e .
```

If new files in the `migrations/versions` directories showed up on the
pull, a database upgrade as detailed below also needs to be run.

## CONFIGURE

Copy the default to the named configuration file

```bash
$ cp $PROJECT_ROOT/application.cfg{.default,}
```

Obtain `consumer_key` and `consumer_secret` values from https://developers.facebook.com/apps  Write the values from Facebook to `application.cfg`:

```bash
# application.cfg
[...]
CONSUMER_KEY = '<App ID From FB>'
CONSUMER_SECRET = '<App Secret From FB>'
```

## Run the Central Services Server
```bash
$ python manage.py runserver
```

## DATABASE

The value of `SQLALCHEMY_DATABASE_URI` defines which database engine
and database to use.  In general, sqlite is used for small testing
instances, and PostgreSQL is used otherwise.

### Migrations

Thanks to Alembic and Flask-Migrate, database migrations are easily
managed and run.

#### Upgrade

Anytime a database (might) need an upgrade, run the manage script with
the `db upgrade` arguments.

This is idempotent process, meaning it's safe to run again on a database
that already received the upgrade.

```bash
python manage.py db upgrade
```

#### Schema Changes

Update the python source files containing table
definitions (typically classes derrived from db.Model) and run the
manage script to sniff out the code changes and generate the necessary
migration steps:

```bash
python manage.py db migrate
```

Then execute the upgrade as previously mentioned:

```bash
python manage.py db upgrade
```

## Testing

All test modules under the `tests` directory can be executed via `nosetests`
(again from project root with the virtual environment activated)

```bash
$ nosetests
```
