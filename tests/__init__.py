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
from portal.models.user import User, Role, UserRoles, add_static_data
from portal.models.fhir import Observation, UserObservation
from portal.models.fhir import CodeableConcept, ValueQuantity

TEST_USER_ID = '5'
TEST_USERNAME = 'testy'
FIRST_NAME = 'First'
LAST_NAME = 'Last'

class TestCase(Base):
    """Base TestClass for application."""

    def create_app(self):
        """Create and return a testing flask app."""

        self.__app = create_app(TestConfig)
        return self.__app

    def init_data(self):
        """Push minimal test data in test database"""
        test_user = User(username=TEST_USERNAME, id=TEST_USER_ID,
                first_name=FIRST_NAME, last_name=LAST_NAME)

        db.session.add(test_user)
        db.session.commit()
        self.promote_user(user_id=test_user.id, role_name='patient')


    def promote_user(self, user_id=TEST_USER_ID, role_name=None):
        """Bless a user with role needed for a test"""
        assert (role_name)
        role_id = db.session.query(Role.id).\
                filter(Role.name==role_name).first()[0]
        db.session.add(UserRoles(user_id=user_id, role_id=role_id))
        db.session.commit()


    def login(self, user_id=TEST_USER_ID):
        """Bless the self.app session with a logged in user

        A standard prerequisite in any test needed an authorized
        user.  Call before subsequent calls to self.app.{get,post,put}

        Taking advantage of testing backdoor in views.auth.login()

        """
        return self.app.get('/login?user_id={0}'.format(user_id),
                follow_redirects=True)


    def setUp(self):
        """Reset all tables before testing."""

        db.create_all()
        add_static_data(db)
        self.init_data()

        self.app = self.__app.test_client()

    def tearDown(self):
        """Clean db session and drop all tables."""

        db.session.remove()
        db.drop_all()
