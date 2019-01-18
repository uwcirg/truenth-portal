Internationalization
********************

.. contents::
   :depth: 3
   :local:

Indicating Translatable Strings
===============================
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

Updating Translation Files
==========================
GNU Gettext translation files consist of a single Portable Object Template file (POT file) and Portable Object (PO file) for each localization (language).

Updating POT files
------------------
To update the .pot file with all source strings from the apptext/interventions tables run the following command::

   $ FLASK_APP=manage.py flask translations

Updating PO files
-----------------
To update the PO files with the latest translations from Smartling, run the following command::

   $ FLASK_APP=manage.py flask download-translations

Initializing Translation Files
==============================
You can create a new .pot file with all extracted translations from the code by running the following pybabel command::

   $ pybabel extract -F instance/babel.cfg -o portal/translations/messages.pot portal/

External Documentation
======================
`jinja i18n-extension <http://jinja.pocoo.org/docs/dev/extensions/#i18n-extension>`_

`gettext <https://docs.python.org/dev/library/gettext.html>`_
