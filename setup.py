""" setup script for "portal" package

see setup.cfg for configuration parameters
for development:
    python setup.py develop

to install:
    python setup.py install

"""
import os

from setuptools import setup

# Detect Heroku build environment and override version generation
# Todo: refactor into setuptools_scm.parse_scm_fallback entrypoint
BUILD_DIR = os.environ.get("BUILD_DIR")
if BUILD_DIR:
    build_version = BUILD_DIR.split("-")[-1]
    setup(version="0+ng" + build_version)
else:
    # default git-based version generation (setuptools-scm), see setup.cfg
    setup()
