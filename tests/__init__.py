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

from portal.factories.app import create_app
from portal.config.config import TestConfig
from portal.extensions import db
from portal.models.assessment_status import invalidate_assessment_status_cache
from portal.models.audit import Audit
from portal.models.client import Client
from portal.models.codeable_concept import CodeableConcept
from portal.models.coding import Coding
from portal.models.coredata import configure_coredata
from portal.models.encounter import Encounter
from portal.models.fhir import CC
from portal.models.fhir import add_static_concepts
from portal.models.intervention import add_static_interventions, INTERVENTION
from portal.models.organization import Organization, add_static_organization
from portal.models.organization import OrgTree
from portal.models.procedure import Procedure
from portal.models.relationship import add_static_relationships
from portal.models.role import Role, add_static_roles, ROLE
from portal.models.tou import ToU
from portal.models.user import User, UserRoles, get_user
from portal.models.user_consent import UserConsent, SEND_REMINDERS_MASK
from portal.models.user_consent import STAFF_EDITABLE_MASK
from portal.models.user_consent import INCLUDE_IN_REPORTS_MASK
from portal.system_uri import SNOMED

TEST_USER_ID = 1
TEST_USERNAME = 'testy@example.com'
FIRST_NAME = u'\u2713'
LAST_NAME = 'Last'
IMAGE_URL = 'http://examle.com/photo.jpg'

# import hidden relation classes needed to create database
from portal.models.communication_request import CommunicationRequest
CommunicationRequest


class TestCase(Base):
    """Base TestClass for application."""

    def create_app(self):
        """Create and return a testing flask app."""

        self._app = create_app(TestConfig)
        return self._app

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
        test_user = db.session.merge(test_user)
        # Avoid testing cached/stale data
        invalidate_assessment_status_cache(test_user.id)
        return test_user

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
        """Bless the self.client session with a logged in user

        A standard prerequisite in any test needed an authorized
        user.  Call before subsequent calls to self.client.{get,post,put}

        Taking advantage of testing backdoor in views.auth.login()

        """
        return self.client.get('/login/TESTING?user_id={0}'.format(user_id),
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

    def add_system_user(self, sponsor=None):
        """create and return system user expected for some tasks """
        sysusername = '__system__'
        if not User.query.filter_by(username=sysusername).first():
            return self.add_user(sysusername, 'System', 'Admin')

    def add_required_clinical_data(self, backdate=None):
        """Add clinical data to get beyond the landing page

        :param backdate: timedelta value.  Define to mock Dx
          happening said period in the past

        """
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        timestamp = None
        if backdate:
            timestamp = datetime.utcnow() - backdate
        for cc in CC.BIOPSY, CC.PCaDIAG, CC.PCaLocalized:
            get_user(TEST_USER_ID).save_constrained_observation(
                codeable_concept=cc, value_quantity=CC.TRUE_VALUE,
                audit=audit, status='preliminary', issued=timestamp)

    def add_procedure(self, code='367336001', display='Chemotherapy',
                      system=SNOMED, setdate=None):
        "Add procedure data into the db for the test user"
        with SessionScope(db):
            audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
            procedure = Procedure(audit=audit)
            coding = Coding(system=system,
                            code=code,
                            display=display).add_if_not_found(True)
            code = CodeableConcept(codings=[coding,]).add_if_not_found(True)
            enc = Encounter(status='planned', auth_method='url_authenticated',
                            user_id=TEST_USER_ID, start_time=datetime.utcnow())
            db.session.add(enc)
            db.session.commit()
            enc = db.session.merge(enc)
            procedure.code = code
            procedure.user = db.session.merge(self.test_user)
            procedure.start_time = setdate or datetime.utcnow()
            procedure.end_time = datetime.utcnow()
            procedure.encounter = enc
            db.session.add(procedure)
            db.session.commit()

    def consent_with_org(self, org_id, user_id=TEST_USER_ID,
                         backdate=None, setdate=None):
        """Bless given user with a valid consent with org

        :param backdate: timedelta value.  Define to mock consents
          happening said period in the past

        :param setdate: datetime value.  Define to mock consents
          happening at exact time in the past

        """
        audit = Audit(user_id=user_id, subject_id=user_id)
        if setdate:
            audit.timestamp = setdate
        elif backdate:
            audit.timestamp = datetime.utcnow() - backdate
        consent = UserConsent(
            user_id=user_id, organization_id=org_id,
            audit=audit, agreement_url='http://fake.org')
        with SessionScope(db):
            db.session.add(consent)
            db.session.commit()

    def bless_with_basics(self, backdate=None, setdate=None):
        """Bless test user with basic requirements for coredata

        :param backdate: timedelta value.  Define to mock consents
          happening said period in the past

        :param setdate: datetime value.  Define to mock consents
          happening at exact time in the past

        """
        self.test_user = db.session.merge(self.test_user)
        self.test_user.birthdate = datetime.utcnow()

        # Register with a clinic
        self.shallow_org_tree()
        org = Organization.query.filter(
            Organization.partOf_id != None).first()
        assert org
        self.test_user.organizations.append(org)

        # Agree to Terms of Use and sign consent
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        if setdate:
            audit.timestamp = setdate
        elif backdate:
            audit.timestamp = datetime.utcnow() - backdate
        tou = ToU(audit=audit, agreement_url='http://not.really.org',
                  type='website terms of use')
        privacy = ToU(audit=audit, agreement_url='http://not.really.org',
                  type='privacy policy')
        parent_org = OrgTree().find(org.id).top_level()
        options = (STAFF_EDITABLE_MASK | INCLUDE_IN_REPORTS_MASK |
                   SEND_REMINDERS_MASK)
        consent = UserConsent(
            user_id=TEST_USER_ID, organization_id=parent_org,
            options=options, audit=audit, agreement_url='http://fake.org')
        with SessionScope(db):
            db.session.add(tou)
            db.session.add(privacy)
            db.session.add(consent)
            db.session.commit()

        # Invalidate org tree cache, in case orgs are added by other
        # tests.  W/o doing so, the new orgs aren't in the orgtree
        OrgTree.invalidate_cache()

    def shallow_org_tree(self):
        """Create shallow org tree for common test needs"""
        org_101 = Organization(id=101, name='101')
        org_102 = Organization(id=102, name='102')
        org_1001 = Organization(id=1001, name='1001', partOf_id=101)
        with SessionScope(db):
            map(db.session.add, (org_101, org_102, org_1001))
            db.session.commit()
        OrgTree.invalidate_cache()

    def deepen_org_tree(self):
        """Create deeper tree when test needs it"""
        self.shallow_org_tree()
        org_l2 = Organization(id=1002, name='l2', partOf_id=102)
        org_l3_1 = Organization(id=10031, name='l3_1', partOf_id=1002)
        org_l3_2 = Organization(id=10032, name='l3_2', partOf_id=1002)
        with SessionScope(db):
            map(db.session.add, (org_l2, org_l3_1, org_l3_2))
            db.session.commit()
        OrgTree.invalidate_cache()

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
        self.init_data()

        # bootstrapping mysteries continue, config variables set during
        # tests don't die; removed unwanted config items if present
        for item in (
                'REQUIRED_CORE_DATA', 'LOCALIZED_AFFILIATE_ORG',
                'ACCEPT_TERMS_ON_NEXT_ORG'):
            if item in self.client.application.config:
                del self.client.application.config[item]

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
