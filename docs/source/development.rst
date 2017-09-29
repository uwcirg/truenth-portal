Development
************

.. contents::
   :depth: 3
   :local:

Context
=================

This documentation is oriented towards supporting CHCR implementation of non-authenticated designs and content: mostly front-end. Note that one complexity is that this code base is used for two different systems/configuations (and more will be added): TrueNTH USA, and ePROMs.

System-specific text (app_text)
===============================

`app_text <configuration.html#apptext>`_

Internationalization (i18n)
===========================
We use gettext for this within python files; we also use `Liferay to manage content in different languages <http://tiny.cc/truenth_liferay#heading=h.ei0lyxrk4ix0>`_.

Surround all strings with ``_( )`` and it will automatically attempt to find a translation, like:

   | _('CELLPHONE')

This should automatically be available in any template file.

.. note::

    we are moving to a model where en_US is used as the key here, with no
    need to use an english .po file.*

For adding new translations, you need to add the blank translation to the .pot file:

   | # <optional comment pointing to where in the code the translation is used>
   | msgid "Cellphone"
   | msgstr ""

You can create a new .pot file with all extracted translations from the code by running the following pybabel command:

   $ pybabel extract -F instance/babel.cfg -o portal/translations/messages.pot portal/
   
You should then update the .pot file with all translation strings from the apptext/interventions tables using the following:

   $ FLASK_APP=manage.py flask translations

You can then use pybabel to update existing .po translation files (this command will only add new translations, it won't remove or modify any existing ones). For example, to update the en_AU translation file::

   $ pybabel update -i portal/translations/messages.pot -d portal/translations -l en_AU --no-wrap

Next, update the new translations in the .po file with the output string:

   | # <optional comment pointing to where in the code the translation is used>
   | msgid "Cellphone"
   | msgstr "Mobile"

Finally, compile all existing .po files into .mo files::

   $ pybabel compile -f -d portal/translations/


Outside documentation `jinja i18n-extension <http://jinja.pocoo.org/docs/dev/extensions/#i18n-extension>`_ and `gettext <https://docs.python.org/dev/library/gettext.html>`_

System-specific pages
=====================

For example, adding a link from the landing page to a "prostate cancer 101" page, but only for TrueNTH (not ePROMs). 
Guidance: use ``SHOW_*`` configurations. See `this example <https://github.com/uwcirg/ePROMs-site-config/blob/master/site_persistence_file.json#L372>`_

Mapping URL's to views
======================

Eg in ``views/patients.py``::

   @patients.route('/patient_profile/<int:patient_id>')

Retrieving content from Liferay
===============================

Note that one of the systems used for this is `AppText <configuration.html#apptext>`_
Information on managing content in Liferay is `here <http://tiny.cc/truenth_liferay>`_

Use of front-end libs
=====================

LESS, jquery, bootstrap, and other 

CSS file - for truenth:
 * ``css/portal.css``
 * ``less/portal.less``

.. note::

   CSS files are compiled from LESS, and that both the CSS and LESS files are managed in git.
   Locally, do ``less portal/static/less/portal.less portal/static/css/portal.css``
   Compilation likely to be moved to deploy.sh, at which point we won't need to manage css files in git.
