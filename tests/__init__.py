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
from portal.models.auth import Client
from portal.models.fhir import ValueQuantity, BIOPSY, PCaDIAG, TX
from portal.models.fhir import Observation, UserObservation
from portal.models.fhir import CodeableConcept, ValueQuantity
from portal.models.fhir import add_static_concepts
from portal.models.intervention import add_static_interventions
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
        else:
            self.test_user = User.query.get(TEST_USER_ID)

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

    def add_test_client(self):
        """Prep db with a test client for test user"""
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER)
        client_id = 'test_client'
        client = Client(client_id=client_id,
                _redirect_uris='http://localhost',
                client_secret='tc_secret', user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(client)
            db.session.commit()
        return db.session.merge(client)

    def add_service_user(self, sponsor=None):
        """create and return a service user for sponsor

        Assign any user to sponsor to use a sponsor other than the default
        test_user

        """
        if not sponsor:
            sponsor = self.test_user
        if not sponsor in db.session:
            sponsor = db.session.merge(sponsor)
        service_user = sponsor.add_service_account()
        with SessionScope(db):
            db.session.add(service_user)
            db.session.commit()
        return db.session.merge(service_user)

    def add_required_clinical_data(self):
        " Add clinical data to get beyond the landing page "
        truthiness = ValueQuantity(value=True, units='boolean')
        for cc in BIOPSY, PCaDIAG, TX:
            self.test_user.save_constrained_observation(
                codeable_concept=cc, value_quantity=truthiness)

    def add_concepts(self):
        """Only tests needing concepts should load - VERY SLOW

        The concept load includes pulling large JSON files, parsing
        and numerous db lookups.  Only load in test if needed.

        """
        with SessionScope(db):
            add_static_concepts()
            db.session.commit()

    def setUp(self):
        """Reset all tables before testing."""

        db.create_all()
        with SessionScope(db):
            # concepts take forever
            # add directly if test needs them
            add_static_interventions()
            add_static_relationships()
            add_static_roles()
            db.session.commit()
        self.init_data()

        self.app = self.__app.test_client()

    def tearDown(self):
        """Clean db session and drop all tables."""

        db.session.remove()
        db.drop_all()
