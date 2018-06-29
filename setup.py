""" setup script for "portal" package

see setup.cfg for configuration parameters
for development:
    python setup.py develop

to install:
    python setup.py install

"""
import os

from setuptools import setup

# Use setuptools-scm to determine version if available (see setup.cfg)
# Todo: refactor into function for setuptools_scm.parse_scm_fallback entrypoint
# Detect Heroku build environment and override version generation (setuptools-scm)
BUILD_DIR = os.environ.get("BUILD_DIR")
if BUILD_DIR:
    build_version = BUILD_DIR.split("-")[-1]
    setup(version="0+ng"+build_version)
else:
    setup()
