""" WSGI Entry Point

"""

from portal.factories.app import create_app
from werkzeug.contrib.fixers import ProxyFix

# WSGI object is named "application" by default
# https://modwsgi.readthedocs.io/en/develop/configuration-directives/WSGICallableObject.html
application = create_app()

if application.config.get('PREFERRED_URL_SCHEME', '').lower() == 'https':
    application.wsgi_app = ProxyFix(application.wsgi_app)
