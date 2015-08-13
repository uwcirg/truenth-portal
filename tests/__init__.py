""" Unit tests for package

to run:
    nosetests

options:
    nosetests --help

"""

from flask.ext.testing import TestCase as Base

from portal.app import create_app
from portal.config import TestConfig
from portal.extensions import db
from portal.models.user import User
from portal.models.fhir import Observation, UserObservation
from portal.models.fhir import CodeableConcept, ValueQuantity

TEST_USER_ID = '5'
FIRST_NAME = 'First'
LAST_NAME = 'Last'

class TestCase(Base):
    """Base TestClass for application."""

    def create_app(self):
        """Create and return a testing flask app."""

        app = create_app(TestConfig)
        return app

    def init_data(self):
        """Push minimal test data in test database"""
        test_user = User(username='testy', id=TEST_USER_ID,
                first_name=FIRST_NAME, last_name=LAST_NAME)
        db.session.add(test_user)
        db.session.commit()

    def setUp(self):
        """Reset all tables before testing."""

        db.create_all()
        self.init_data()

    def tearDown(self):
        """Clean db session and drop all tables."""

        db.session.remove()
        db.drop_all()
