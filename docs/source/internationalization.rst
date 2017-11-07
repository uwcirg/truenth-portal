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
