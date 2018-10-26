Configuration
*************

TruenNTH Shared Services can be configured in a number of fashions, to support
a variety of use cases.

Three primary mechanisms are in place to setup the system as desired:

- `Flask Configuration Files`_
- `Site Persistence`_
- `AppText`_

Flask Configuration Files
=========================
Flask configuration files (``.cfg``) are simple python files used to set Flask configuration parameters.

application.cfg
---------------
This primary configuration file lives in the `instance` source directory.
See `README <readme_link.html>`__ for initial setup of ``application.cfg``.

Only values unique to a particular install belong in `application.cfg`
including:

1. passwords
2. keys / secrets
3. filesystem paths or local connection details

All others should likely be handled by `Site Persistence`_.

Values with defaults are typically defined in the ``portal.config.BaseConfig``
class.  Most are self explanatory or include inline comments for clarification.

Of special note, the one used to control which set of values are pulled in
by `Site Persistence`_.

PERSISTENCE_DIR::

    See also Site Persistence, this controls which persistence directory the
    `FLASK_APP=manage.py flask sync` command uses to load persistence data
    and build the `site.cfg` file.  The value is relative to the
    `portal/config` directory.

    For TrueNTH:

        PERSISTENCE_DIR='gil'

    For ePROMs:

        PERSISTENCE_DIR='eproms'

site.cfg
--------
This configuration file also lives in the `instance` source directory, but
unlike `application.cfg`_, it is managed by `Site Persistence`_.  It houses
the configuration variables used to define the look of the site, such as
those use to differentiate `ePROMs` from `TrueNTH`.

A few worthy of special mention for the task of customizing Shared Services.

REQUIRED_CORE_DATA::

    Set to control what portions of data are considered *required* prior
    to allowing the user to transition beyond initial_queries.  Expects
    a list, with the following options:

    REQUIRED_CORE_DATA = ['name', 'dob', 'role', 'org', 'clinical', 'tou']

PORTAL_STYLESHEET::

    Define which stylesheet to include.  Defaults to 'css/portal.css'

    For ePROMs:

    PORTAL_STYLESHEET = 'css/eproms.css'

To update the ``site.cfg`` file contents, edit the
``site_persistence_file.json`` file or use the ``FLASK_APP=manage.py flask export-site``
command and commit the changed ``site_persistence_file.json`` to the
appropriate repository.

base.cfg
--------
An optional configuration file loaded before `application.cfg`_, useful for setting infrastructure-specific defaults.

Site Persistence
================

In order to handle the migration of **site specific** data, one can generate or
import a persistence file, housing details such as:

- business rules defining when interventions should be presented to users
- customization of intervention text
- organizations and clinics on the site

The ``portal.SitePersistence`` class manages the import and export of 
the ``site.cfg`` configuration file as well as a
number of database tables holding significant data required for a rich
experience.  This should never include any patient or personal data, but
will include codified business rules and required data to support them.

Database tables included:

- AccessStrategies
- AppText
- CommunicationRequest
- Interventions
- Organizations
- Questionnaires
- QuestionnaireBanks
- ScheduledJobs

Both importing and exporting use the value of ``PERSISTENCE_DIR``.
Its value is initially looked for as an environment variable, and if not
found, the configuration value of 'GIL' is used.  (With 'GIL' set, the `gil`
configuration directory is used, otherwise, `eproms`).

Export
------
Site persistence files can be generated in the ``PERSISTENCE_DIR``.  See
above for correct setting.  To generate persistence files from current
database values, execute::

```FLASK_APP=manage.py flask export-site```

Import
------
As a final step in the ``seed`` process, site persistence brings the
respective database tables in sync, and generates the `site.cfg`_ config file:

```FLASK_APP=manage.py flask seed```

Detailed logging will inform the user of changes made.

.. note::

    It may be wise to back up the existing database prior to running ``python
    manage.py seed`` in the unlikely event of unwanted overwrites or deletes.


AppText
=======

To avoid near duplication of templates needing only a few minor string changes,
the ``portal.models.AppText`` class (and its surrogate ``apptext`` database
table), provide a mechanism for customizing individual strings.

In a template, in place of a static string, insert a jinja2 variable string
calling the `app_text` function, including the unique name of the string
to be customized.  For example, in the `portal.templates.layout.html` file,
the value of the title string is imported via::

    <title>{{ app_text('layout title') }}</title>

The value for such an AppText can be manually inserted in the database, or
added to the site persistence file.  Such an entry looks like::

    {
      "custom_text": "Movember ePROMs",
      "name": "layout title",
      "resourceType": "AppText"
    },

AppText can also handle positional arguments as well as references to
configuration values to fill in dynamic values within a string.  The
positional arguments are zero indexed, and must be defined when the template
is rendered (i.e. JavaScript variables will not be properly defined until
the script is evaluated within the browser, and will therefore not work).

For example, given the application has the configuration
value ``USER_APP_NAME`` set to ``TrueNTH`` and the following::

    AppText(name='ex', custom_text='Welcome to {config[USER_APP_NAME]}, {0}. {1} {0}')

A template including::

    <p>{{ app_text('ex', 'Bob', 'Goodbye') }}</p>

Would render::

    <p>Welcome to TrueNTH, Bob. Goodbye Bob</p>
