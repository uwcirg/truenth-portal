Provider Authentication
***********************
.. contents::
   :depth: 3
   :local:

OAuth Workflow
=================
In order for a user to access authenticated portal pages they first need to login. When logging in through a 3rd party, such as Facebook or Google, the OAuth workflow is used. In this workflow, after the user clicks on the 3rd party's login button they're taken to the 3rd party's login page where they enter their credentials. Upon successful login the 3rd party passes the portal an access token that allows us to fetch information from the third party on the user's behalf which we use to update the user's account and log them in to our system.

Underneath the hood we use `Flask-Dance <https://github.com/singingwolfboy/flask-dance>`_. At a high level, Flask-Dance uses blueprints to authenticate with providers and returns control to our APIs when auth succeeds or fails. The blueprints and APIs are defined in ``portal/views/auth.py``. Upon successful authentication the ``login()`` API is called with the user's access/bearer token which we use to get info about the user. To get this info we create an instance of ``FacebookFlaskDanceProvider`` or ``GoogleFlaskDanceProvider``, which both inherit from ``FlaskDanceProvider``, and call ``get_user_info``. This function uses the user's access token to send an authenticated request to the provider. When the request returns with the user's information we use create the user an account if they've never logged in before or update an existing account if they've logged in using a different provider, and finally log them in to the current session. All of this logic takes place in ``login_user_with_provider()``.

Configuration
=================
In order to authenticate users the portal must know the public and private keys to each 3rd party application. If you haven't already, you'll need to create a third party app and copy its configuration values to ``instance/application.cfg`` by following the steps below:

.. _oauthconfig:

Facebook
~~~~~~~~
To enable Facebook OAuth, create a new app on `Facebook's App page <https://developers.facebook.com/apps>`_ and copy the ``consumer_key`` and ``consumer_secret`` to ``application.cfg``:

.. code:: bash

    # application.cfg
    [...]
    FACEBOOK_OAUTH_CLIENT_ID = '<App ID From FB>'
    FACEBOOK_OAUTH_CLIENT_SECRET = '<App Secret From FB>'

-  Set the ``Authorized redirect URIs`` to exactly match the location of ``<scheme>://<hostname>/login/facebook/``
-  Set the deauthorize callback. Go to your app, then choose **Products**, then **Facebook Login**, and finally **Settings**. A text field is provided for the Deauthorize Callback URL. Enter ``<scheme>://<hostname>/deauthorized``

Google
~~~~~~
To enable Google OAuth, create a new app on `Google's API page <https://console.developers.google.com/project/_/apiui/credential?pli=1>`_ and copy the ``consumer_key`` and ``consumer_secret`` to ``application.cfg``:

.. code:: bash

    # application.cfg
    [...]
    GOOGLE_OAUTH_CLIENT_ID = '<App ID From Google>'
    GOOGLE_OAUTH_CLIENT_SECRET = '<App Secret From Google>'

-  Under APIs Credentials, select ``OAuth 2.0 client ID``
-  Set the ``Authorized redirect URIs`` to exactly match the location of ``<scheme>://<hostname>/login/google/``
-  Enable the ``Google+ API``

activate
~~~~~~~~~~
In a **non-production** environment add the following to the bottom of ``env/bin/activate``:

.. code:: bash

    export OAUTHLIB_RELAX_TOKEN_SCOPE=1
    export OAUTHLIB_INSECURE_TRANSPORT=1

In a **production** environment you should **only** add the following to the bottom of ``env/bin/activate``:

.. code:: bash

    export OAUTHLIB_RELAX_TOKEN_SCOPE=1

`Explination <https://flask-dance.readthedocs.io/en/latest/quickstarts/google.html?highlight=OAUTHLIB_RELAX_TOKEN_SCOPE>`_

Adding a new provider
======================
To add a new provider you'll need to

1.  Create a new blueprint in ``portal/views/auth.py`` (see the ``google_blueprint`` and ``facebook_blueprint`` as examples and use `Flask-Dance Documentation <https://flask-dance.readthedocs.io/en/latest/>`_ as a reference)
2.  Update the existing callback API functions ``login()`` and ``provider_oauth_error`` to use your new blueprint (see examples from Google and Facebook blueprints in ``portal/views/auth.py``)
3.  Create a new class in ``portal/models/flaskdanceprovider.py`` that inherits from FlaskDanceProvider and overrides get_user_info to get user info from the provider (see ``FacebookFlaskDanceProvider`` and ``GoogleFlaskDanceProvider`` for examples)
4.  Import the class created in #3 into ``portal/views/auth.py`` and create a new instance of it when ``login()`` is called by the new provider (see how ``FacebookFlaskDanceProvider`` and ``GoogleFlaskDanceProvider`` are used in ``login()`` for reference)
