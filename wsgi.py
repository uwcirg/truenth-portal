""" WSGI Entry Point

"""

from werkzeug.middleware.proxy_fix import ProxyFix

from portal.factories.app import create_app

# WSGI object is named "application" by default
# https://modwsgi.readthedocs.io/en/develop/configuration-directives/WSGICallableObject.html
application = create_app()

if application.config.get('PREFERRED_URL_SCHEME', '').lower() == 'https':
    application.wsgi_app = ProxyFix(application.wsgi_app)
