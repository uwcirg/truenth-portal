""" Unit tests for package

to run:
    nosetests

options:
    nosetests --help

"""

from flask.ext.testing import TestCase as Base
from flask.ext.webtest import SessionScope

from portal.app import create_app
from portal.config import TestConfig
from portal.extensions import db
from portal.models.fhir import Observation, UserObservation
from portal.models.fhir import CodeableConcept, ValueQuantity
from portal.models.relationship import add_static_relationships
from portal.models.role import Role, add_static_roles, ROLE
from portal.models.user import User, UserRoles

TEST_USER_ID = 1
TEST_USERNAME = 'testy'
FIRST_NAME = 'First'
LAST_NAME = 'Last'
IMAGE_URL = 'http://examle.com/photo.jpg'

class TestCase(Base):
    """Base TestClass for application."""

    def create_app(self):
        """Create and return a testing flask app."""

        self.__app = create_app(TestConfig)
        return self.__app

    def init_data(self):
        """Push minimal test data in test database"""
        test_user_id = self.add_user(username=TEST_USERNAME,
                first_name=FIRST_NAME, last_name=LAST_NAME,
                image_url=IMAGE_URL)
        if test_user_id != TEST_USER_ID:
            print "apparent cruft from last run (test_user_id: %d)"\
                    % test_user_id
            print "try again..."
            self.tearDown()
            self.setUp()

    def add_user(self, username, first_name="", last_name="", image_url=None):
        """Create a user with default role

        Returns the newly created user id

        """
        test_user = User(username=username, first_name=first_name,
                last_name=last_name, image_url=image_url)

        with SessionScope(db):
            db.session.add(test_user)
            db.session.commit()

        test_user = db.session.merge(test_user)
        self.promote_user(user_id=test_user.id,
                role_name=ROLE.PATIENT)
        test_user = db.session.merge(test_user)
        return test_user.id

    def promote_user(self, user_id=TEST_USER_ID, role_name=None):
        """Bless a user with role needed for a test"""
        assert (role_name)
        role_id = db.session.query(Role.id).\
                filter(Role.name==role_name).first()[0]
        with SessionScope(db):
            db.session.add(UserRoles(user_id=user_id, role_id=role_id))
            db.session.commit()

    def login(self, user_id=TEST_USER_ID):
        """Bless the self.app session with a logged in user

        A standard prerequisite in any test needed an authorized
        user.  Call before subsequent calls to self.app.{get,post,put}

        Taking advantage of testing backdoor in views.auth.login()

        """
        return self.app.get('/login/TESTING?user_id={0}'.format(user_id),
                follow_redirects=True)

    def setUp(self):
        """Reset all tables before testing."""

        db.create_all()
        with SessionScope(db):
            add_static_relationships()
            add_static_roles()
        self.init_data()

        self.app = self.__app.test_client()

    def tearDown(self):
        """Clean db session and drop all tables."""

        db.session.remove()
        db.drop_all()
