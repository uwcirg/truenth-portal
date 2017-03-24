""" setup script for "portal" package

for development:
    python setup.py develop

to install:
    python setup.py install

"""

from setuptools import setup

project = "portal"

# maintain long_description as a single long line.
# workaround for a bug in pkg_info._get_metadata("PKG-INFO")
long_description =\
"""TrueNTH Shared Services RESTful API, to be used by TrueNTH intervention applications. This API attempts to conform with the HL7 FHIR specification as much as is reasonable.
"""

setup(
    name=project,
    url="https://github.com/uwcirg/true_nth_usa_portal",
    description="TrueNTH Shared Services",
    long_description=long_description,
    author="CIRG, University of Washington",
    author_email="truenth-dev@uw.edu",
    maintainer="CIRG, University of Washington",
    maintainer_email="truenth-dev@uw.edu",
    classifiers=(
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Scientific/Engineering :: Medical Science Apps",
    ),
    license = "BSD",
    platforms = "any",

    include_package_data=True,
    use_scm_version=True,
    zip_safe=False,
    packages=["portal"],
    scripts=["manage.py"],
    setup_requires=("setuptools_scm"),
    install_requires=(
        "Authomatic",
        "celery",
        "enum34",
        "Flask",
        "Flask-Babel",
        "Flask-Celery-Helper",
        "Flask-Migrate",
        "Flask-OAuthlib",
        "Flask-SQLAlchemy",
        "Flask-Script",
        "Flask-Session",
        "Flask-Swagger",
        "Flask-Testing",
        "Flask-User",
        "Flask-WebTest",
        "fuzzywuzzy",
        "jsonschema",
        "oauthlib",
        "pkginfo",
        "psycopg2",
        "python-dateutil",
        "python-Levenshtein",
        "redis",
        "requests-cache",
        "shellvars-py",
        "sphinx",
        "sphinx_rtd_theme",
        "validators",
    ),
    extras_require = {
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
