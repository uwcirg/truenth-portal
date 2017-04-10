Timeouts
********

Session timeouts are handled slightly differently in the browser and on the server hosting Shared Services.

Backend
=======

After authenticating with Shared Services, a cookie is set with an expiration time corresponding to the value of :term:`PERMANENT_SESSION_LIFETIME`, in seconds. If no requests are made in that duration, the cookie and corresponding redis-backed session automatically expire (via TTL). Subsequent requests will be effectively be unauthenticated and force redirection to the login page.

The backend session (the cookie and corresponding redis entry) can be refreshed from the front-end by sending a POST request to ``/api/ping`` that will modify the current backend session, refreshing the timeout duration (to the value specified by :term:`PERMANENT_SESSION_LIFETIME`).


Frontend
========

The browser is made aware of the session duration specified by :term:`PERMANENT_SESSION_LIFETIME` and will prompt a user to refresh their session one minute before it expires, but cannot reliably determine the remaining time in the backend session because it may have been refreshed in another tab or browser window.


Intervention
============

After authenticating with Shared Services, interventions are granted access through a bearer token that expires after a duration set by :term:`OAUTH2_PROVIDER_TOKEN_EXPIRES_IN` (defaults to 4 hours).

Subsequent requests with the same bearer token refresh its expiration each time.

.. glossary::

    PERMANENT_SESSION_LIFETIME
        The lifetime of a permanent session, defaults to one hour. Configures session cookie and corresponding redis-backed session. Configuration value `provided by Flask
        <http://flask.pocoo.org/docs/0.12/config/#builtin-configuration-values>`_.

    OAUTH2_PROVIDER_TOKEN_EXPIRES_IN
        Bearer token expires time, defaults to four hours. Configuration value provided by `Flask-OAuthlib
        <https://flask-oauthlib.readthedocs.io/en/latest/oauth2.html#configuration>`_.
