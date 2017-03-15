"""WSGI api to pull environment in from common docker/.env file"""
import os
import shellvars

env_file = os.path.join(os.path.dirname(__file__), '../docker/.env')
def import_env():
    """Pull variables defined in env_file into os.environ

    Only expected to be called from WSGI file.  virtualenvwrapper users
    should pull in same environment values using the postactivate
    script.

    """
    if os.path.exists(env_file):
        for var, value in shellvars.get_vars(env_file).items():
            os.environ[var] = value
