""" setup script for "portal" package

for development:
    python setup.py develop

to install:
    python setup.py install

"""
import datetime
import os

from setuptools import setup

setup_kwargs = dict(
    scripts=[
        "manage.py",
        "wsgi.py",
        os.path.join('docker', 'remap_envvars.py'),
    ],
    test_suite="tests",
)

# Use setuptools-scm to determine version if available
# Todo: refactor into function for setuptools_scm.parse_scm_fallback entrypoint
version_kwargs = dict(
    use_scm_version=True,
    setup_requires=('setuptools_scm'),
)

# Detect Heroku build environment and override version generation (setuptools-scm)
BUILD_DIR = os.environ.get("BUILD_DIR")
if BUILD_DIR:
    build_version = BUILD_DIR.split("-")[-1]
    version_kwargs = {"version": "0+ng"+build_version}

setup_kwargs.update(version_kwargs)
setup(**setup_kwargs)
