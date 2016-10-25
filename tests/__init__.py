""" Unit tests for package

to run:
    nosetests

options:
    nosetests --help

"""
from datetime import datetime
from flask_testing import TestCase as Base
from flask_webtest import SessionScope
from sqlalchemy.exc import IntegrityError

from portal.app import create_app
from portal.config import TestConfig
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.auth import Client
from portal.models.fhir import CC
from portal.models.fhir import add_static_concepts
from portal.models.intervention import add_static_interventions, INTERVENTION
from portal.models.organization import Organization, add_static_organization
from portal.models.organization import OrgTree
from portal.models.relationship import add_static_relationships
from portal.models.role import Role, add_static_roles, ROLE
from portal.models.tou import ToU
from portal.models.user import User, UserRoles
from portal.models.user_consent import UserConsent
from portal.site_persistence import SitePersistence

TEST_USER_ID = 1
TEST_USERNAME = 'testy@example.com'
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
        try:
            test_user = self.add_user(username=TEST_USERNAME,
                    first_name=FIRST_NAME, last_name=LAST_NAME,
                    image_url=IMAGE_URL)
        except IntegrityError:
            db.session.rollback()
            test_user = User.query.filter_by(username=TEST_USERNAME).one()
            print "found existing test_user at {}".format(test_user.id)

        if test_user.id != TEST_USER_ID:
            print "apparent cruft from last run (test_user_id: %d)"\
                    % test_user.id
            print "try again..."
            self.tearDown()
            self.setUp()
        else:
            self.test_user = test_user

    def add_user(self, username, first_name="", last_name="", image_url=None):
        """Create a user and add to test db, and return it"""
        test_user = User(username=username, first_name=first_name,
                last_name=last_name, image_url=image_url)
        with SessionScope(db):
            db.session.add(test_user)
            db.session.commit()
        return db.session.merge(test_user)

    def promote_user(self, user=None, role_name=None):
        """Bless a user with role needed for a test"""
        if not user:
            user = self.test_user
        user = db.session.merge(user)
        assert (role_name)
        role_id = db.session.query(Role.id).\
                filter(Role.name==role_name).first()[0]
        with SessionScope(db):
            db.session.add(UserRoles(user_id=user.id, role_id=role_id))
            db.session.commit()

    def login(self, user_id=TEST_USER_ID):
        """Bless the self.app session with a logged in user

        A standard prerequisite in any test needed an authorized
        user.  Call before subsequent calls to self.app.{get,post,put}

        Taking advantage of testing backdoor in views.auth.login()

        """
        return self.app.get('/login/TESTING?user_id={0}'.format(user_id),
                follow_redirects=True)

    def add_client(self):
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
        for cc in CC.BIOPSY, CC.PCaDIAG, CC.TX, CC.PCaLocalized:
            self.test_user.save_constrained_observation(
                codeable_concept=cc, value_quantity=CC.TRUE_VALUE,
                audit=Audit(user_id=TEST_USER_ID))

    def bless_with_basics(self):
        """Bless test user with basic requirements for coredata"""
        self.test_user.birthdate = datetime.utcnow()

        # Register with a clinic
        org = Organization(name='fake urology clinic')
        self.test_user.organizations.append(org)

        # Agree to Terms of Use and sign consent
        audit = Audit(user_id=TEST_USER_ID)
        tou = ToU(audit=audit, text="filler text")
        consent = UserConsent(user_id=TEST_USER_ID, organization=org,
                              audit=audit, agreement_url='http://fake.org')
        with SessionScope(db):
            db.session.add(tou)
            db.session.add(consent)
            db.session.commit()

    def add_concepts(self):
        """Only tests needing concepts should load - VERY SLOW

        The concept load includes pulling large JSON files, parsing
        and numerous db lookups.  Only load in test if needed.

        """
        with SessionScope(db):
            add_static_concepts(only_quick=False)
            db.session.commit()

    def setUp(self):
        """Reset all tables before testing."""

        db.drop_all()  # clean up from previous tests
        db.create_all()
        with SessionScope(db):
            # concepts take forever, only load the quick ones.
            # add directly (via self.add_concepts()) if test needs them
            add_static_concepts(only_quick=True)
            add_static_interventions()
            add_static_organization()
            add_static_relationships()
            add_static_roles()
            db.session.commit()
            SitePersistence().import_()
        self.init_data()

        self.app = self.__app.test_client()

    def tearDown(self):
        """Clean db session.

        Database drop_all is done at setup due to app context challenges with
        LiveServerTestCase (it cleans up its context AFTER tearDown()
        is called)

        """
        db.session.remove()
        db.engine.dispose()

        # lazyprops can't survive a db purge - purge cached attributes
        for attr in dir(CC):
            if attr.startswith('_lazy'):
                delattr(CC, attr)
        for attr in dir(INTERVENTION):
            if attr.startswith('_lazy'):
                delattr(INTERVENTION, attr)
        OrgTree.invalidate_cache()
