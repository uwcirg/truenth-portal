""" setup script for 'portal' package

for development:
    python setup.py develop

to install:
    python setup.py install

"""

from setuptools import setup

project = "portal"

setup(
    name=project,
    version='0.1',
    url='https://github.com/uwcirg/true_nth_usa_portal_demo',
    description='Movember Truenth USA Portal',
    author='University of Washington',
    packages=["portal"],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'Authomatic',
        'Flask>=0.10.1',
        'Flask-Migrate',
        'Flask-OAuthlib',
        'Flask-SQLAlchemy',
        'Flask-Script',
        'Flask-Testing',
        'nose',
        'oauthlib',
        'psycopg2',
        'python-dateutil',
    ],
    test_suite='tests',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: Healthcare Industry',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'Topic :: Scientific/Engineering :: Medical Science Apps',
    ]
)
