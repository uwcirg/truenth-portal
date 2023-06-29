# -*- coding: utf-8 -*-
""" Unit tests for package

to run:
    py.test

options:
    py.test --help

"""

from datetime import datetime
from time import sleep

from flask import url_for
from flask_testing import TestCase as Base
from flask_webtest import SessionScope
from sqlalchemy.exc import IntegrityError

from portal.cache import cache
from portal.config.config import TestConfig
from portal.database import db
from portal.date_tools import utcnow_sans_micro
from portal.factories.app import create_app
from portal.models.audit import Audit
from portal.models.client import Client
from portal.models.clinical_constants import CC, add_static_concepts
from portal.models.codeable_concept import CodeableConcept
from portal.models.coding import Coding
from portal.models.communication_request import CommunicationRequest
from portal.models.encounter import Encounter
from portal.models.identifier import Identifier
from portal.models.intervention import INTERVENTION, add_static_interventions
from portal.models.organization import (
    Organization,
    OrgTree,
    add_static_organization,
)
from portal.models.practitioner import Practitioner
from portal.models.procedure import Procedure
from portal.models.qb_timeline import invalidate_users_QBT
from portal.models.questionnaire_bank import add_static_questionnaire_bank
from portal.models.questionnaire import Questionnaire
from portal.models.relationship import add_static_relationships
from portal.models.research_study import add_static_research_studies
from portal.models.role import ROLE, Role, add_static_roles
from portal.models.tou import ToU
from portal.models.user import User, UserRoles
from portal.models.user_consent import (
    INCLUDE_IN_REPORTS_MASK,
    SEND_REMINDERS_MASK,
    STAFF_EDITABLE_MASK,
    UserConsent,
)
from portal.system_uri import (
    SNOMED,
    TRUENTH_PI,
    TRUENTH_QUESTIONNAIRE_CODE_SYSTEM,
    US_NPI,
)

DEFAULT_PASSWORD = 'fakePa$$'

TEST_USER_ID = 1
TEST_USERNAME = 'testy@example.com'
FIRST_NAME = '✓'
LAST_NAME = 'Last'
IMAGE_URL = 'http://examle.com/photo.jpg'

OAUTH_INFO_PROVIDER_LOGIN = {
    'birthdate': '10/04/1988',
    'email': 'test@test.com',
    'first_name': 'Firstname',
    'gender': 'male',
    'last_name': 'Lastname',
    'image_url': 'pictureurl@example.com',
    'next': '/',
    'provider_id': '12345678910',
    'provider_name': 'google',
    'token': '{ "property": "value" }',
}

# cheap reference to hidden relation classes needed to create database
CommunicationRequest


def associative_backdate(now, backdate):
    """Correct non-associative relative-delta month math

    :param now: datetime start point
    :param backdate: relativedelta value to move back from now.

    Asking for a relative delta back in time for a period of months and
    then adding the same number of months does NOT always produce the
    same starting value.  For example May 30 - 3 months => Feb 28/29 depending
    on leap year determination.  Adding 3 months to Feb 28 always produces
    May 28.

    Work around this problem by returning a backdated datetime value, that is
    by reducing now by the backdate, and also return a ``nowish`` datetime
    value, either equal to now or adjusted to make the pair associative,
    such that:

        nowish - backdate == result + backdate == nowish

    Therefore nowish will typically be equal to now, but altered in boundary
    cases for tests needing this associative property.

    :returns: backdated_datetime, nowish

    """
    result = now - backdate
    return result, result + backdate


def calc_date_params(backdate, setdate):
    """
    Returns the calculated date given user's request

    Tests frequently need to mock times, this returns the calculated time,
    either by adjusting from utcnow (via backdate), using the given value
    (in setdate) or using the value of now if neither of those are available.

    :param backdate: a relative timedelta to move from now
    :param setdate: a specific datetime value
    :return: best date given parameters

    """
    if setdate and backdate:
        raise ValueError("set ONE, `backdate` OR `setdate`")

    if setdate:
        acceptance_date = setdate
    elif backdate:
        # Guard against associative problems with backdating by
        # months.
        if backdate.months:
            raise ValueError(
                "moving dates by month values is non-associative; use"
                "`associative_backdate` and pass in `setdate` param")
        acceptance_date = utcnow_sans_micro() - backdate
    else:
        acceptance_date = utcnow_sans_micro()
    return acceptance_date


class TestCase(Base):
    """Base TestClass for application."""

    def create_app(self):
        """Create and return a testing flask app."""

        self._app = create_app(TestConfig)
        return self._app

    def init_data(self):
        """Push minimal test data in test database"""
        try:
            test_user = self.add_user(
                username=TEST_USERNAME, first_name=FIRST_NAME,
                last_name=LAST_NAME, image_url=IMAGE_URL)
        except IntegrityError:
            db.session.rollback()
            test_user = User.query.filter_by(username=TEST_USERNAME).one()
            print("found existing test_user at {}".format(test_user.id))

        if test_user.id != TEST_USER_ID:
            print("apparent cruft from last run (test_user_id: %d)"
                  % test_user.id)
            print("try again...")
            self.tearDown()
            self.setUp()
        else:
            self.test_user = test_user

    def add_user(
            self, username, first_name="", last_name="", image_url=None,
            password=DEFAULT_PASSWORD, email=None):
        """Create a user and add to test db, and return it"""
        # Hash the password
        password = self.app.user_manager.hash_password(password)

        test_user = User(
            username=username, first_name=first_name, last_name=last_name,
            image_url=image_url, password=password)
        if email is not None:
            test_user.email = email
        with SessionScope(db):
            db.session.add(test_user)
            db.session.commit()
        test_user = db.session.merge(test_user)
        # Avoid testing cached/stale data
        invalidate_users_QBT(test_user.id, research_study_id='all')
        return test_user

    def add_user_identifier(self, user=None, system=None, value=None):
        if not user:
            user = self.test_user
        ident = Identifier(system=system, _value=value).add_if_not_found()
        user.add_identifier(ident)

    def promote_user(self, user=None, role_name=None):
        """Bless a user with role needed for a test"""
        if not user:
            user = self.test_user
        user = db.session.merge(user)
        assert (role_name)
        role_id = db.session.query(Role.id).filter(
            Role.name == role_name).first()[0]
        with SessionScope(db):
            db.session.add(UserRoles(user_id=user.id, role_id=role_id))
            db.session.commit()

    def login(
        self,
        user_id=TEST_USER_ID,
        oauth_info=None,
        follow_redirects=True
    ):
        """login using the oauth backdoor

        A standard prerequisite in any test needed an authorized
        user. Call before subsequent calls to self.client.{get,post,put}
        or call to test oauth logic.

        Taking advantage of testing backdoor in
        views.auth.oauth_test_backdoor()

        """
        # By default log the user in through the session
        # with the given id
        if not oauth_info:
            oauth_info = {'user_id': user_id}

        # Attempt to login using the test backdoor
        return self.client.get(
            'test/oauth',
            query_string=oauth_info,
            follow_redirects=follow_redirects
        )

    def local_login(self, email, password, follow_redirects=True):
        """logs in a local user through user.login view"""
        url = url_for('user.login')
        return self.client.post(
            url,
            data={
                'email': email,
                'password': password,
            },
            follow_redirects=follow_redirects
        )

    def add_client(self):
        """Prep db with a test client for test user"""
        self.promote_user(role_name=ROLE.APPLICATION_DEVELOPER.value)
        client_id = 'test_client'
        client = Client(
            client_id=client_id, _redirect_uris='http://localhost',
            client_secret='tc_secret', user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(client)
            db.session.commit()
        return db.session.merge(client)

    @staticmethod
    def add_questionnaire(name):
        q = Questionnaire()
        i = Identifier(
            system=TRUENTH_QUESTIONNAIRE_CODE_SYSTEM, value=name)
        q.identifiers.append(i)
        with SessionScope(db):
            db.session.add(q)
            db.session.commit()
        return db.session.merge(q)

    def add_service_user(self, sponsor=None):
        """create and return a service user for sponsor

        Assign any user to sponsor to use a sponsor other than the default
        test_user

        """
        if not sponsor:
            sponsor = self.test_user
        if sponsor not in db.session:
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
            sys_user = self.add_user(sysusername, 'System', 'Admin')
        self.promote_user(sys_user, ROLE.ADMIN.value)
        return sys_user

    def add_required_clinical_data(self, backdate=None, setdate=None):
        """Add clinical data to get beyond the landing page

        :param backdate: timedelta value.  Define to mock Dx
          happening said period in the past
        :param setdate: datetime value.  Define to mock Dx
          happening at given time

        """
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        for cc in CC.BIOPSY, CC.PCaDIAG, CC.PCaLocalized:
            User.query.get(TEST_USER_ID).save_observation(
                codeable_concept=cc, value_quantity=CC.TRUE_VALUE,
                audit=audit, status='preliminary', issued=calc_date_params(
                    backdate=backdate, setdate=setdate))

    @staticmethod
    def add_practitioner(
            first_name='first', last_name='last', id_value='12345'):
        p = Practitioner(first_name=first_name, last_name=last_name)
        i = Identifier(system=US_NPI, value=id_value)
        p.identifiers.append(i)
        with SessionScope(db):
            db.session.add(p)
            db.session.commit()
        p = db.session.merge(p)
        return p

    @staticmethod
    def add_primary_investigator(
            first_name='first', last_name='last', email='pi@example.com'):
        pi = User(first_name=first_name, last_name=last_name, email=email)
        i = Identifier(system=TRUENTH_PI, value=True)
        pi.identifiers.append(i)
        with SessionScope(db):
            db.session.add(pi)
            db.session.commit()
        pi = db.session.merge(pi)
        return pi

    def add_procedure(self, code='367336001', display='Chemotherapy',
                      system=SNOMED, setdate=None):
        "Add procedure data into the db for the test user"
        with SessionScope(db):
            audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
            procedure = Procedure(audit=audit)
            coding = Coding(
                system=system,
                code=code,
                display=display).add_if_not_found(True)
            code = CodeableConcept(codings=[coding]).add_if_not_found(True)
            enc = Encounter(
                status='planned',
                auth_method='url_authenticated',
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

        NB - if existing consent for user/org is present, simply update
        with new date values

        :param backdate: timedelta value.  Define to mock consents
          happening said period in the past

        :param setdate: datetime value.  Define to mock consents
          happening at exact time in the past

        """
        # doesn't make sense to consent w/o an association, add if missing
        user = User.query.get(user_id)
        if org_id not in (o.id for o in user.organizations):
            user.organizations.append(Organization.query.get(org_id))

        acceptance_date = calc_date_params(
            backdate=backdate, setdate=setdate)
        consent = UserConsent.query.filter(
            UserConsent.user_id == user_id).filter(
            UserConsent.organization_id == org_id).first()
        if consent:
            consent.acceptance_date = acceptance_date
        else:
            audit = Audit(user_id=user_id, subject_id=user_id)
            consent = UserConsent(
                user_id=user_id, organization_id=org_id,
                audit=audit, agreement_url='http://fake.org',
                research_study_id=0,
                acceptance_date=acceptance_date)
        with SessionScope(db):
            if consent not in db.session:
                db.session.add(consent)
            db.session.commit()

    def bless_with_basics(
            self, user=None, backdate=None, setdate=None,
            local_metastatic=None, make_patient=True):
        """Bless user with basic requirements for coredata

        :param user: user to bless, self.test_user by default
        :param backdate: timedelta value.  Define to mock consents
          happening said period in the past.  See
          ``associative_backdate`` for issues with 'months'.
        :param setdate: datetime value.  Define to mock consents
          happening at exact time in the past
        :param local_metastatic: set to 'localized' or 'metastatic' for
          tests needing those respective orgs assigned to the user
        :param make_patient: add patient role unless set False

        """
        if not user:
            user = db.session.merge(self.test_user)
        else:
            user = db.session.merge(user)
        user_id = user.id
        user.birthdate = datetime.utcnow()

        if make_patient:
            self.promote_user(user=user, role_name=ROLE.PATIENT.value)

        # Register with a clinic
        self.shallow_org_tree()

        if local_metastatic:
            org = Organization.query.filter(
                Organization.name == local_metastatic).one()
        else:
            org = Organization.query.filter(
                Organization.partOf_id.isnot(None)).first()
        assert org
        user = db.session.merge(user)
        user.organizations.append(org)

        # Agree to Terms of Use and sign consent
        audit = Audit(user_id=user_id, subject_id=user_id)
        tou = ToU(
            audit=audit, agreement_url='http://not.really.org',
            type='website terms of use')
        privacy = ToU(
            audit=audit, agreement_url='http://not.really.org',
            type='privacy policy')
        web_consent = ToU(
            audit=audit, agreement_url='http://not.really.org',
            type='subject website consent')
        parent_org = OrgTree().find(org.id).top_level()
        options = (STAFF_EDITABLE_MASK | INCLUDE_IN_REPORTS_MASK |
                   SEND_REMINDERS_MASK)
        consent = UserConsent(
            user_id=user_id, organization_id=parent_org,
            options=options, audit=audit, agreement_url='http://fake.org',
            research_study_id=0,
            acceptance_date=calc_date_params(
                backdate=backdate, setdate=setdate))
        with SessionScope(db):
            db.session.add(tou)
            db.session.add(privacy)
            db.session.add(web_consent)
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

        already_done = Organization.query.get(101)
        if already_done:
            return

        with SessionScope(db):
            [db.session.add(org) for org in (org_101, org_102, org_1001)]
            db.session.commit()
        OrgTree.invalidate_cache()

    def deepen_org_tree(self):
        """Create deeper tree when test needs it"""
        self.shallow_org_tree()
        org_l2 = Organization(id=1002, name='l2', partOf_id=102)
        org_l3_1 = Organization(id=10031, name='l3_1', partOf_id=1002)
        org_l3_2 = Organization(id=10032, name='l3_2', partOf_id=1002)
        with SessionScope(db):
            [db.session.add(org) for org in (org_l2, org_l3_1, org_l3_2)]
            db.session.commit()
        OrgTree.invalidate_cache()

    def prep_org_w_identifier(self):
        o = Organization(name='test org')
        i = Identifier(system=US_NPI, value='123-45')
        o.identifiers.append(i)
        with SessionScope(db):
            db.session.add(o)
            db.session.commit()
        o = db.session.merge(o)
        return o

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
        # NB - if the drop_all call ever hangs, it's typically a symptom
        # of an open handle to the test db - perhaps from celery workers.
        db.drop_all()  # clean up from previous tests
        db.create_all()
        with SessionScope(db):
            # concepts take forever, only load the quick ones.
            # add directly (via self.add_concepts()) if test needs them
            add_static_concepts(only_quick=True)
            add_static_interventions()
            add_static_organization()
            add_static_questionnaire_bank()
            add_static_relationships()
            add_static_research_studies()
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

        # Removed potentially cached data from other tests
        cache.clear()

    def results_from_async_call(
            self, url, timeout=5, include_task_path=False, query_string=None):
        """Wrap task of obtaining results from an async request"""
        response = self.client.get(url, query_string=query_string)
        # expect 202 response with location of status
        assert response.status_code == 202
        status_url = response.headers.get('Location')

        # Give task a number of one second pauses to complete
        for i in range(0, timeout):
            response = self.client.get(status_url)
            if response.json['state'] == 'SUCCESS':
                break
            sleep(1)

        if response.json['state'] != 'SUCCESS':
            print(response.json)
            raise RuntimeError(response.json)

        # done, now pull result (chop /status from status url for task result)
        task_path = status_url[:-len('/status')]
        results = self.client.get(task_path)
        if include_task_path:
            return task_path, results
        return results
