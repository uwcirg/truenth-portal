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
$ sudo apt-get install python-virtualenv libffi-dev redis-server
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
about missing dependencies.

```bash
$ cd $PROJECT_HOME
$ source env/bin/activate
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
$ pip install --process-dependency-links -e .
```

If you would like to contribute to this project or run the test suite run `pip` as follows. This will install the default dependencies and all of the dependencies required for running the test suite and contributing.

```bash
$ pip install --process-dependency-links -e .[dev]
```

If new files in the `migrations/versions` directories showed up on the
pull, a database upgrade as detailed below also needs to be run.

## CONFIGURE

Copy the default to the named configuration file

```bash
$ cp $PROJECT_HOME/portal/application.cfg{.default,}
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


## Documentation

Docs are built seperately via sphinx.  Change to the docs directory and use
the contained Makefile to build - then view in browser starting with the
`docs/build/html/index.html` file

```bash
$ cd docs
$ make html
```
