Timeouts
********

Session timeouts are handled slightly differently in the browser and on the server hosting Shared Services.

Backend
=======

After authenticating with the portal a cookie is set with an expiration time corresponding to the value of ``PERMANENT_SESSION_LIFETIME``, in seconds. If no requests are made in that duration, the cookie and corresponding redis-backed session automatically expire (via TTL). Subsequent requests will be effectively be unauthenticated and force redirection to the login page.

The backend session (the cookie and corresponding redis entry) can be refreshed from the front-end by sending a POST request to ``/api/ping`` that will modify the current backend session, refreshing the timeout duration (to the value specified by ``PERMANENT_SESSION_LIFETIME``).


Frontend
========

The browser is made aware of the session duration specified by ``PERMANENT_SESSION_LIFETIME`` and will prompt a user to refresh their session one minute before it expires, but cannot reliably determine the remaining time in the backend session because it may have been refreshed in another tab or browser window.
