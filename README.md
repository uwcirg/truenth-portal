# true_nth_usa_portal
Movember TrueNTH USA Shared Services

## INSTALLATION

Pick any path for installation

```bash
$ export PROJECT_HOME=~/truenth_ss
```

### Prerequisites (done one time)

#### Install required packages

```bash
$ sudo apt-get install postgresql python-virtualenv python-dev
$ sudo apt-get install libffi-dev libpq-dev build-essential redis-server
```

#### Clone the Project

```bash
$ git clone https://github.com/uwcirg/true_nth_usa_portal.git $PROJECT_HOME
```

#### Create a Virtual Environment

This critical step enables isolation of the project from system python,
making dependency maintenance easier and more stable.  It does require
that you ```activate``` the virtual environment before you interact
with python or the installer scripts.  The virtual environment can be
installed anywhere, using the nested 'env' pattern here.

```bash
$ virtualenv $PROJECT_HOME/env
```

#### Activate the Virtual Environment

Required to interact with the python installed in this virtual
environment.  Forgetting this step will result in obvious warnings
about missing dependencies. This needs to be done in every shell session that you work from.

```bash
$ cd $PROJECT_HOME
$ source env/bin/activate
```

#### Create the Database

To create the postgresql database that backs your Shared Services issue the following commands:

```bash
$ sudo -u postgres createuser truenth-dev --pwprompt # enter password at prompt
$ sudo -u postgres createdb truenth-dev --owner truenth-dev
```

#### Update pip
The OS default version of pip is often out of date and may need to be updated before it is able to install other project dependencies:

```bash
$ pip install --upgrade pip setuptools
```

## CONFIGURE

Copy the default to the named configuration file

```bash
$ cp $PROJECT_HOME/instance/application.cfg{.default,}
```

Obtain `consumer_key` and `consumer_secret` values from https://developers.facebook.com/apps  Write the values from Facebook to `application.cfg`:

```bash
# application.cfg
[...]
FB_CONSUMER_KEY = '<App ID From FB>'
FB_CONSUMER_SECRET = '<App Secret From FB>'
```

To enable Google OAuth, obtain similar values from
https://console.developers.google.com/project/_/apiui/credential?pli=1

- Under APIs Credentials, select `OAuth 2.0 client ID`
- Set the `Authorized redirect URIs` to exactly match the location of `<scheme>://<hostname>/login/google/`
- Enable the `Google+ API`

Write to the respective GOOGLE_CONSUMER_KEY and GOOGLE_CONSUMER_SECRET
variables in the same `application.cfg` configuration file.

### Install the Lastest Package (and Dependencies)

To update your Shared Services installation run the `deploy.sh` script as described below.

This script will:
* Update the project with the latest code
* Install any dependencies, if necessary
* Perform any database migrations, if necessary
* Seed any new data to the database, if necessary
* Restart apache, if served by apache

```bash
$ cd $PROJECT_HOME
$ ./bin/deploy.sh -fv # -f to force a run, -v for verbose output
```

When running deploy.sh for the first time, add the -i flag to initialize the database. Do not add this flag when running deploy.sh on a working database.

```bash
$ cd $PROJECT_HOME
$ ./bin/deploy.sh -fvi # -i to initialize the database
```

To see all available options run:

```bash
$ ./bin/deploy.sh -h
```

## Run the Central Services Server
```bash
$ python manage.py runserver
```

## Run the Celery Worker
```bash
$ celery worker -A portal.celery_worker.celery --loglevel=info
```

Alternatively, install an init script and configure.  See
http://docs.celeryproject.org/en/latest/tutorials/daemonizing.html

## DATABASE

The value of `SQLALCHEMY_DATABASE_URI` defines which database engine
and database to use.  At this time, only PostgreSQL is supported.

### Migrations

Thanks to Alembic and Flask-Migrate, database migrations are easily
managed and run.

Note::

    Alembic tracks the current version of the database to determine which
    migration scripts to apply.  After the initial install, stamp the current
    version for subsequent upgrades to succeed:

    `python manage.py db stamp head`

#### Upgrade

Anytime a database (might) need an upgrade, run the manage script with
the `db upgrade` arguments (or run the [deployment script](#install-the-lastest-package-and-dependencies))

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

To run the tests, repeat the ``postgres createuser && postgres createdb``
commands as above with the values for the {user, password, database}
as defined in the `TestConfig` class within ``portal.config.py``

All test modules under the `tests` directory can be executed via `nosetests`
(again from project root with the virtual environment activated)

```bash
$ nosetests
```

Alternatively, run a single modules worth of tests, telling nose to not
supress standard out (vital for debugging) and to stop on first error:

```bash
$ nosetests -sx tests.test_intervention
```

The test suite can also be run on different python interpreters (currently Python 2.7, 3.5 and PyPy), if available, using the tox test automation framework:

```bash
$ tox
```

Tox will pass any options after -- to the test runner, nose, eg:

```bash
$ tox -- -sx tests.test_intervention
```
### Continuous Integration

This project includes integration with the [TravisCI continuous integration platform](https://docs.travis-ci.com/user/languages/python/). The full test suite (every Tox virtual environment) is [automatically run](https://travis-ci.org/uwcirg/true_nth_usa_portal) for the last commit pushed to any branch, and for all pull requests. Results are reported as passing with a &#10004; and failing with a &#10006;.

#### UI/Integration (Selenium) Testing

UI integration/acceptance testing is performed by Selenium and is included in the test suite and continuous intergration setup. Specifically, [Sauce Labs integration](https://docs.travis-ci.com/user/sauce-connect) with TravisCI allows Selenium tests to be run with any number of browser/OS combinations and [captures video from running tests](https://saucelabs.com/open_sauce/user/ivan-c).

UI tests can also be run locally (after installing `xvfb`) by passing Tox the virtual environment that corresponds to the UI tests (`ui`):
```bash
$ tox -e ui
```

## Dependency Management

Project dependencies are hardcoded to specific versions (see `requirements.txt`) known to be compatible with Shared Services to prevent dependency updates from breaking existing code.

If pyup.io integration is enabled the service will create pull requests when individual dependencies are updated, allowing the project to track the latest dependencies. These pull requests should be merged without need for review, assuming they pass continuous integration.

## Documentation

Docs are built seperately via sphinx.  Change to the docs directory and use
the contained Makefile to build - then view in browser starting with the
`docs/build/html/index.html` file

```bash
$ cd docs
$ make html
```

