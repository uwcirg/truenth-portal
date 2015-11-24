import os, sys

PROJECT_DIR = os.path.join(os.path.dirname(__file__))
# activate virtualenv
activate_this = os.path.join(PROJECT_DIR, 'env/bin/activate_this.py')
execfile(activate_this, dict(__file__=activate_this))

if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from portal.app import create_app
application = create_app()
