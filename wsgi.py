""" WSGI Entry Point

"""

from portal.factories.app import create_app
from werkzeug.contrib.fixers import ProxyFix

# WSGI apps are called "application" by default
application = create_app()

if application.config.get('PREFERRED_URL_SCHEME', '').lower() == 'https':
    application.wsgi_app = ProxyFix(application.wsgi_app)
