""" WSGI Entry Point

"""

from portal.app import create_app
from werkzeug.contrib.fixers import ProxyFix

app = create_app()

if app.config.get('PREFERRED_URL_SCHEME', '').lower() == 'https':
    app.wsgi_app = ProxyFix(app.wsgi_app)
