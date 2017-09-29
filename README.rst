true\_nth\_usa\_portal
======================

Movember TrueNTH USA Shared Services

INSTALLATION
------------

Pick any path for installation

.. code:: bash

    $ export PROJECT_HOME=~/truenth_ss

Prerequisites (done one time)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install required packages
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: bash

    $ sudo apt-get install postgresql python-virtualenv python-dev
    $ sudo apt-get install libffi-dev libpq-dev build-essential redis-server

Clone the Project
^^^^^^^^^^^^^^^^^

.. code:: bash

    $ git clone https://github.com/uwcirg/true_nth_usa_portal.git $PROJECT_HOME

Create a Virtual Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This critical step enables isolation of the project from system python,
making dependency maintenance easier and more stable. It does require
that you ``activate`` the virtual environment before you interact with
python or the installer scripts. The virtual environment can be
installed anywhere, using the nested 'env' pattern here.

.. code:: bash

    $ virtualenv $PROJECT_HOME/env

Activate the Virtual Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Required to interact with the python installed in this virtual
environment. Forgetting this step will result in obvious warnings about
missing dependencies. This needs to be done in every shell session that
you work from.

.. code:: bash

    $ cd $PROJECT_HOME
    $ source env/bin/activate

Create the Database
^^^^^^^^^^^^^^^^^^^

To create the postgresql database that backs your Shared Services issue
the following commands:

.. code:: bash

    $ sudo -u postgres createuser truenth-dev --pwprompt # enter password at prompt
    $ sudo -u postgres createdb truenth-dev --owner truenth-dev

Update pip
^^^^^^^^^^

The OS default version of pip is often out of date and may need to be
updated before it is able to install other project dependencies:

.. code:: bash

    $ pip install --upgrade pip setuptools

CONFIGURE
---------

Copy the default to the named configuration file

.. code:: bash

    $ cp $PROJECT_HOME/instance/application.cfg{.default,}

Obtain ``consumer_key`` and ``consumer_secret`` values from
`Facebook App page <https://developers.facebook.com/apps>`__ and write the values to
``application.cfg``:

.. code:: bash

    # application.cfg
    [...]
    FB_CONSUMER_KEY = '<App ID From FB>'
    FB_CONSUMER_SECRET = '<App Secret From FB>'

To enable Google OAuth, obtain similar values from the `Google API page <https://console.developers.google.com/project/_/apiui/credential?pli=1>`__.

-  Under APIs Credentials, select ``OAuth 2.0 client ID``
-  Set the ``Authorized redirect URIs`` to exactly match the location of
   ``<scheme>://<hostname>/login/google/``
-  Enable the ``Google+ API``

Write to the respective GOOGLE\_CONSUMER\_KEY and
GOOGLE\_CONSUMER\_SECRET variables in the same ``application.cfg``
configuration file.

Install the Lastest Package (and Dependencies)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To update your Shared Services installation run the ``deploy.sh`` script
as described below.

This script will: \* Update the project with the latest code \* Install
any dependencies, if necessary \* Perform any database migrations, if
necessary \* Seed any new data to the database, if necessary \* Restart
apache, if served by apache

.. code:: bash

    $ cd $PROJECT_HOME
    $ ./bin/deploy.sh -fv # -f to force a run, -v for verbose output

When running deploy.sh for the first time, add the -i flag to initialize
the database. Do not add this flag when running deploy.sh on a working
database.

.. code:: bash

    $ cd $PROJECT_HOME
    $ ./bin/deploy.sh -fvi # -i to initialize the database

To see all available options run:

.. code:: bash

    $ ./bin/deploy.sh -h

Run the Central Services Server
-------------------------------

.. code:: bash

    $ FLASK_APP=manage.py flask runserver

Run the Celery Worker
---------------------

.. code:: bash

    $ celery worker --app portal.celery_worker.celery --loglevel=info

Alternatively, install an init script and configure. See `Daemonizing Celery <http://docs.celeryproject.org/en/latest/tutorials/daemonizing.html>`__

Should the need ever arise to purge the queue of jobs, run the following destructive command

.. code:: bash

    $ celery -A portal.celery_worker.celery purge

DATABASE
--------

The value of ``SQLALCHEMY_DATABASE_URI`` defines which database engine
and database to use. At this time, only PostgreSQL is supported.

Migrations
~~~~~~~~~~

Thanks to Alembic and Flask-Migrate, database migrations are easily
managed and run.

.. note:: Alembic tracks the current version of the database to determine which
   migration scripts to apply.  After the initial install, stamp the current
   version for subsequent upgrades to succeed:

.. code:: bash

    FLASK_APP=manage.py flask db stamp head

Upgrade
^^^^^^^

Anytime a database (might) need an upgrade, run the manage script with
the ``db upgrade`` arguments (or run the `deployment
script <#install-the-lastest-package-and-dependencies>`__)

This is idempotent process, meaning it's safe to run again on a database
that already received the upgrade.

.. code:: bash

    FLASK_APP=manage.py flask db upgrade

Schema Changes
^^^^^^^^^^^^^^

Update the python source files containing table definitions (typically
classes derrived from db.Model) and run the manage script to sniff out
the code changes and generate the necessary migration steps:

.. code:: bash

    FLASK_APP=manage.py flask db migrate

Then execute the upgrade as previously mentioned:

.. code:: bash

    FLASK_APP=manage.py flask db upgrade

Testing
-------

To run the tests, repeat the
``postgres createuser && postgres createdb`` commands as above with the
values for the {user, password, database} as defined in the
``TestConfig`` class within ``portal.config.py``

All test modules under the ``tests`` directory can be executed via
``nosetests`` (again from project root with the virtual environment
activated)

.. code:: bash

    $ nosetests

Alternatively, run a single modules worth of tests, telling nose to not
supress standard out (vital for debugging) and to stop on first error:

.. code:: bash

    $ nosetests -sx tests.test_intervention

Tox
~~~

The test runner `Tox
<https://tox.readthedocs.io/en/latest/>`__ is configured to run the portal test suite and test other parts of the build process, each configured as a separate Tox "environment". To run all available environments, execute the following command:

.. code:: bash

    $ tox

To run a specific tox environment, "docs" or the docgen environment in this case, invoke tox with the ``-e`` option eg:

.. code:: bash

    $ tox -e docs

Tox will also run the environment specified by the ``TOXENV`` environmental variable, as configured in the TravisCI integration.

Tox will pass any options after -- to the test runner, nose. To run tests only from a certain module (analgous the above nosetests invocation):

.. code:: bash

    $ tox -- -sx tests.test_intervention

Continuous Integration
~~~~~~~~~~~~~~~~~~~~~~

This project includes integration with the `TravisCI continuous
integration
platform <https://docs.travis-ci.com/user/languages/python/>`__. The
full test suite (every Tox virtual environment) is `automatically
run <https://travis-ci.org/uwcirg/true_nth_usa_portal>`__ for the last
commit pushed to any branch, and for all pull requests. Results are
reported as passing with a ✔ and failing with a ✖.

UI/Integration (Selenium) Testing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

UI integration/acceptance testing is performed by Selenium and is
included in the test suite and continuous intergration setup.
Specifically, `Sauce Labs
integration <https://docs.travis-ci.com/user/sauce-connect>`__ with
TravisCI allows Selenium tests to be run with any number of browser/OS
combinations and `captures video from running
tests <https://saucelabs.com/open_sauce/user/ivan-c>`__.

UI tests can also be run locally (after installing ``xvfb``) by passing
Tox the virtual environment that corresponds to the UI tests (``ui``):

.. code:: bash

    $ tox -e ui

Dependency Management
---------------------

Project dependencies are hardcoded to specific versions (see
``requirements.txt``) known to be compatible with Shared Services to
prevent dependency updates from breaking existing code.

If pyup.io integration is enabled the service will create pull requests
when individual dependencies are updated, allowing the project to track
the latest dependencies. These pull requests should be merged without
need for review, assuming they pass continuous integration.

Documentation
-------------

Docs are built seperately via sphinx. Change to the docs directory and
use the contained Makefile to build - then view in browser starting with
the ``docs/build/html/index.html`` file

.. code:: bash

    $ cd docs
    $ make html
