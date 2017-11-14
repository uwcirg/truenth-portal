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
