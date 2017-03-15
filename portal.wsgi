# WSGI entry point
#
# NB - the python-home variable must be defined and point to the
# root of the virtualenv - see:
#   http://modwsgi.readthedocs.io/en/develop/user-guides/virtual-environments.html

from portal.app import create_app
from portal.env import import_env


import_env()
application = create_app()
