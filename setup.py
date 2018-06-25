""" setup script for "portal" package

for development:
    python setup.py develop

to install:
    python setup.py install

"""
import datetime
import os

from setuptools import find_packages, setup

setup_kwargs = dict(
    include_package_data=True,
    zip_safe=False,
    packages=find_packages(),
    scripts=[
        "manage.py",
        "wsgi.py",
        os.path.join('docker', 'remap_envvars.py'),
    ],
    install_requires=[
        "Authomatic",
        "celery",
        "enum34",
        "Flask",
        "Flask-Babel",
        "Flask-Dogpile-Cache",
        "Flask-Migrate",
        "Flask-OAuthlib",
        "Flask-Recaptcha",
        "Flask-SQLAlchemy",
        "Flask-Session",
        "Flask-Swagger",
        "Flask-Testing",
        "Flask-User",
        "Flask-WebTest",
        "fuzzywuzzy",
        "gunicorn",
        "jsonschema",
        "oauthlib",
        "pkginfo",
        "polib",
        "psycopg2",
        "python-dateutil",
        "python-Levenshtein",
        "redis",
        "requests-cache",
        "regex",
        "sphinx",
        "sphinx_rtd_theme",
        "validators",
    ],
    extras_require={
        "dev": (
            "coverage",
            "nose",
            "page_objects",
            "selenium",
            "swagger_spec_validator",
            "tox",
            "xvfbwrapper",
        ),
    },
    test_suite="tests",
)

# Use setuptools-scm to determine version if available
# Todo: refactor into function for setuptools_scm.parse_scm_fallback entrypoint
if os.path.exists('.git'):
    version_kwargs = dict(
        use_scm_version=True,
        setup_requires=('setuptools_scm'),
    )
else:
    # Detect Heroku build environment
    BUILD_DIR = os.environ.get("BUILD_DIR", None)
    if BUILD_DIR:
        # Override version generation (setuptools-scm)
        build_version = BUILD_DIR.split("-")[-1]
        version_kwargs = {"version": "0+ng"+build_version}

    else:
        version_kwargs = dict(
            version='0+d'+datetime.date.today().strftime('%Y%m%d'))

setup_kwargs.update(version_kwargs)
setup(**setup_kwargs)
