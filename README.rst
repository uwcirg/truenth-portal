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

.. _activate-venv:

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

Building the schema and populating with basic configured values is done via
the :ref:`flask sync <flask-sync>` command.  See details below.

Update pip
^^^^^^^^^^

The default version of pip provided in the virtual environment is often out
of date.  Best to update first, for optimal results:

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

.. _pip:

Install the Latest Package and Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Instruct ``pip`` to install the correct version of all dependencies into the
virtual environment. This idempotent step can be run anytime to confirm the
correct libraries are installed:

.. code:: bash

    pip install --requirement requirements.txt

COMMAND LINE INTERFACE
----------------------

A number of built in and custom extensions for command line interaction are
available via the `click command line interface <http://click.pocoo.org/>`_,
several of which are documented below.

To use or view the usage of the available commands:

1. :ref:`activate-venv`
2. Set **FLASK_APP** environment variable to point at **manage.py**

.. code:: bash

    export FLASK_APP=manage.py

3. Issue the ``flask --help`` or ``flask <cmd> --help`` commands for more details

.. code:: bash

    flask sync --help

.. note:: All ``flask`` commands mentioned within this document require the
    first two steps listed above.

.. _flask-sync:

Sync Database and Config Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The idempotent ``sync`` function takes necessary steps to build tables,
upgrade the database schema and run ``seed`` to populate with static data.
Safe to run on existing or brand new databases.

.. code:: bash

    flask sync

Add User
~~~~~~~~

Especially useful in bootstrapping a new install, a user may be added and
blessed with the admin role from the command line.  Be sure to use a secure
password.

.. code:: bash

    flask add_user --email user@server.com --password reDacted! --role admin

Password Reset
~~~~~~~~~~~~~~

Users who forget their passwords should be encouraged to use the **forgot
password** link from the login page.  In rare instances when direct password
reset is necessary, an admin may perform the following:

.. code:: bash

    flask --email forgotten_user@server.com --password newPassword --actor <admin's email>

Install the Latest Package, Dependencies and Synchronize DB (via script)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To update your Shared Services installation run the ``deploy.sh`` script
(this process wraps together pulling the latest from the repository, the
:ref:`pip <pip>` and :ref:`flask sync <flask-sync>` commands listed above).

This script will:

* Update the project with the latest code
* Install any dependencies, if necessary
* Perform any database migrations, if necessary
* Seed any new data to the database, if necessary

.. code:: bash

    $ cd $PROJECT_HOME
    $ ./bin/deploy.sh

To see all available options run:

.. code:: bash

    $ ./bin/deploy.sh -h

Run the Shared Services Server
-------------------------------
To run the flask development server, run the below command from an activated virtual environment

.. code:: bash

    $ flask run

By default the flask dev server will run without the debugger and listen on port 5000 of localhost. To override these defaults, call ``flask run`` as follows

.. code:: bash

    $ FLASK_DEBUG=1 flask run --port 5001 --host 0.0.0.0

Run the Celery Worker
---------------------

.. code:: bash

    $ celery worker --app portal.celery_worker.celery --loglevel=info

Alternatively, install an init script and configure. See
`Daemonizing Celery <http://docs.celeryproject.org/en/latest/tutorials/daemonizing.html>`__

Should the need ever arise to purge the queue of jobs, run the following
**destructive** command

.. code:: bash

    $ celery --app portal.celery_worker.celery purge

DATABASE
--------

The value of ``SQLALCHEMY_DATABASE_URI`` defines which database engine
and database to use.  Alternatively, the following environment
variables may be used (and if defined, will be preferred):

#. ``PGDATABASE``
#. ``PGUSER``
#. ``PGPASSWORD``
#. ``PGHOST``

At this time, only PostgreSQL is supported.

Migrations
~~~~~~~~~~

Thanks to Alembic and Flask-Migrate, database migrations are easily
managed and run.

.. note:: Alembic tracks the current version of the database to determine which
   migration scripts to apply.  After the initial install, stamp the current
   version for subsequent upgrades to succeed:

.. code:: bash

    flask db stamp head

.. note:: The :ref:`flask sync <flask-sync>` command covers this step automatically.

Upgrade
^^^^^^^

Anytime a database (might) need an upgrade, run the manage script with
the ``db upgrade`` arguments (or run the `deployment
script <#install-the-latest-package-and-dependencies>`__)

This is idempotent process, meaning it's safe to run again on a database
that already received the upgrade.

.. code:: bash

    flask db upgrade

.. note:: The :ref:`flask sync <flask-sync>` command covers this step automatically.

Schema Changes
^^^^^^^^^^^^^^

Update the python source files containing table definitions (typically
classes derived from db.Model) and run the manage script to sniff out
the code changes and generate the necessary migration steps:

.. code:: bash

    flask db migrate

Then execute the upgrade as previously mentioned:

.. code:: bash

    flask db upgrade

Testing
-------

To run the tests, repeat the
``postgres createuser && postgres createdb`` commands as above with the
values for the {user, password, database} as defined in the
``TestConfig`` class within ``portal\config\config.py``

All test modules under the ``tests`` directory can be executed via
``py.test`` (again from project root with the virtual environment
activated)

.. code:: bash

    $ py.test

Alternatively, run a single modules worth of tests, telling py.test to not
suppress standard out (vital for debugging) and to stop on first error:

.. code:: bash

    $ py.test tests/test_intervention.py

Tox
~~~

The test runner `Tox
<https://tox.readthedocs.io/en/latest/>`__ is configured to run the portal test suite and test other parts of the build process, each configured as a separate Tox "environment". To run all available environments, execute the following command:

.. code:: bash

    $ tox

To run a specific tox environment, "docs" or the docgen environment in this case, invoke tox with the ``-e`` option eg:

.. code:: bash

    $ tox -e docs

Tox will also run the environment specified by the ``TOXENV`` environment variable, as configured in the TravisCI integration.

Tox will pass any options after -- to the test runner, py.test. To run tests only from a certain module (analogous the above py.test invocation):

.. code:: bash

    $ tox -- tests/test_intervention.py

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
included in the test suite and continuous integration setup.
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

Project dependencies are hard-coded to specific versions (see
``requirements.txt``) known to be compatible with Shared Services to
prevent dependency updates from breaking existing code.

If pyup.io integration is enabled the service will create pull requests
when individual dependencies are updated, allowing the project to track
the latest dependencies. These pull requests should be merged without
need for review, assuming they pass continuous integration.

Documentation
-------------

Docs are built separately via sphinx. Change to the docs directory and
use the contained Makefile to build - then view in browser starting with
the ``docs/build/html/index.html`` file

.. code:: bash

    $ cd docs
    $ make html


POSTGRESQL WINDOWS INSTALLATION GUIDE
-------------------------------------

Download
~~~~~~~~

Download PostgreSQL via:
https://www.postgresql.org/download/windows/

Creating the Database and User
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To create the postgresql database, in pgAdmin click "databases" and "create"
and enter the desired characteristics of the database, including the owner.
To create the user, similarly in pgAdmin, click "login roles" and "create"
and enter the desired characteristics of the user. Ensure that it has
permission to login.

Configuration
~~~~~~~~~~~~~

Installing requirements
^^^^^^^^^^^^^^^^^^^^^^^

Ensure that C++ is installed -- if not, download from:
https://www.microsoft.com/en-us/download/details.aspx?id=44266

Ensure that ``setuptools`` is up-to-date by running:

.. code:: bash

    $ python -m pip install --upgrade pip setuptools

Ensure that ``ez_setup`` is installed by running:

.. code:: bash

    $ pip install ez_setup

Install requirements by running:

.. code:: bash

    $ pip install --requirement requirements.txt

Configuration files
^^^^^^^^^^^^^^^^^^^

In ``$PATH\\data\pg_hba.conf`` , change the bottom few lines to read::

    # TYPE  DATABASE        USER            ADDRESS                 METHOD

    # IPv4 local connections:

    host    all             all             127.0.0.1/32            trust

    # IPv6 local connections:

    host    all             all             ::1/128                 trust


Copy the default configuration file to the named configuration file

.. code:: bash

    $ copy $PROJECT_HOME/instance/application.cfg.default $PROJECT_HOME/instance/application.cfg

In ``application.cfg``, (below), fill in the values for ``SQLALCHEMY_DATABASE_URI`` for user, password,
localhost, portnum, and dbname.

user, password, and dbname were setup earlier in pgAdmin.

portnum can also be found in pgAdmin.

localhost should be 127.0.0.1

``SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@localhost:portnum/dbname'``

Testing
~~~~~~~

To test that the database is set up correctly, from a virtual environment run:

.. code:: bash

    $ python ./bin/testconnection.py
