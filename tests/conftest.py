# test plugin
# https://docs.pytest.org/en/latest/writing_plugins.html#conftest-py-plugins
from datetime import datetime

from flask import url_for
from flask_webtest import SessionScope
import pytest
from urllib.parse import urlparse, urljoin

from portal.cache import cache
from portal.config.config import TestConfig
from portal.database import db
from portal.factories.app import create_app
from portal.factories.celery import create_celery
from portal.models.audit import Audit
from portal.models.client import Client
from portal.models.clinical_constants import add_static_concepts
from portal.models.intervention import add_static_interventions
from portal.models.organization import Organization, OrgTree, add_static_organization
from portal.models.qb_timeline import invalidate_users_QBT
from portal.models.relationship import add_static_relationships
from portal.models.role import ROLE, Role, add_static_roles
from portal.models.tou import ToU
from portal.models.user import User, UserRoles
from portal.models.user_consent import (
    INCLUDE_IN_REPORTS_MASK,
    SEND_REMINDERS_MASK,
    STAFF_EDITABLE_MASK,
    UserConsent,
)
from tests import TEST_USER_ID 


def pytest_addoption(parser):
    parser.addoption(
        "--include-ui-testing",
        action="store_true",
        default=False,
        help="run selenium ui tests",
    )


def shallow_org_tree():
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
        acceptance_date = datetime.utcnow() - backdate
    else:
        acceptance_date = datetime.utcnow()
    return acceptance_date


@pytest.fixture(scope="session")
def initialize_static(initialized_db):
    def initialize_static():
        add_static_concepts(only_quick=True)
        add_static_interventions()
        add_static_organization()
        add_static_relationships()
        add_static_roles()
        db.session.commit()
    return initialize_static


@pytest.fixture(scope="session")
def app(request):
    """Fixture to use as parameter in any test needing app access

    NB - use of pytest-flask ``client`` fixture is more common

    """
    app_ = create_app(TestConfig)
    ctx = app_.app_context()
    ctx.push()

    def teardown():
        ctx.pop()

    request.addfinalizer(teardown)
    return app_


@pytest.fixture(scope="session")
def app_logger(app):
    """fixture for functions requiring current_app.logger"""
    return app.logger


@pytest.fixture(scope='session')
def initialized_db(app, request):
    """Create database schema"""
    db.drop_all()
    db.create_all()


@pytest.fixture(autouse=True)
def teardown_db(app, request):
    def teardown():
        cache.clear()
        db.session.remove()
        db.engine.dispose()
        db.drop_all()
        db.create_all()

    request.addfinalizer(teardown)


@pytest.fixture(scope='session')
def celery_worker_parameters():
    # type: () -> Mapping[str, Any]
    """Redefined like fixture from celery.contrib.pytest.py as instructed

    Specifically, we need to extend the default queues so the celery worker
    will process tasks given to either queue.

    The dict returned by your fixture will then be used
    as parameters when instantiating :class:`~celery.worker.WorkController`.
    """
    return {
        'queues': ('celery', 'low_priority'),
        'perform_ping_check': False}


@pytest.fixture(scope='session')
def celery_app(app):
    """Fixture to use as parameter in any test needing celery"""
    celery = create_celery(app)

    # bring celery_worker fixture into scope
    from celery.contrib.testing import tasks  # NOQA

    return celery


@pytest.fixture
def test_user(app, add_user, initialized_db):
    DEFAULT_PASSWORD = 'fakePa$$'
    TEST_USERNAME = 'test@example.com'
    FIRST_NAME = '✓'
    LAST_NAME = 'Last'
    IMAGE_URL = 'http://examle.com/photo.jpg'

    test_user = add_user(
            username=TEST_USERNAME, first_name=FIRST_NAME,
            last_name=LAST_NAME, image_url=IMAGE_URL)
    yield test_user


@pytest.fixture
def add_user(app, initialized_db):
    def add_user(
            username, first_name="", last_name="",
            image_url=None, password="fakePa$$", email=None):
        """Create a user and add to test db, and return it"""
        # Hash the password
        password = app.user_manager.hash_password(password)

        test_user = User(
            username=username, first_name=first_name,
            last_name=last_name, image_url=image_url, password=password)
        if email is not None:
            test_user.email = email
        with SessionScope(db):
            db.session.add(test_user)
            db.session.commit()
        test_user = db.session.merge(test_user)
        # Avoid testing cached/stale data
        invalidate_users_QBT(test_user.id)
        return test_user
    yield add_user


@pytest.fixture
def add_service_user(initialize_static, test_user):
    def add_service_user(sponsor=None):
        initialize_static()

        if not sponsor:
            sponsor = test_user
        if sponsor not in db.session:
            sponsor = db.session.merge(sponsor)
        service_user = sponsor.add_service_account()
        with SessionScope(db):
            db.session.add(service_user)
            db.session.commit()

        return db.session.merge(service_user)
    return add_service_user


@pytest.fixture
def bless_with_basics(test_user, promote_user):
    def bless_with_basics(
            user=None, backdate=None, setdate=None,
            local_metastatic=None, make_patient=True):
        """Bless user with basic requirements for coredata

        :param user: user to bless, test_user by default
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
            user = db.session.merge(test_user)
        else:
            user = db.session.merge(user)
        user_id = user.id
        user.birthdate = datetime.utcnow()

        if make_patient:
            promote_user(user=user, role_name=ROLE.PATIENT.value)

        # Register with a clinic
        shallow_org_tree()

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
        parent_org = OrgTree().find(org.id).top_level()
        options = (STAFF_EDITABLE_MASK | INCLUDE_IN_REPORTS_MASK |
                   SEND_REMINDERS_MASK)
        consent = UserConsent(
            user_id=user_id, organization_id=parent_org,
            options=options, audit=audit, agreement_url='http://fake.org',
            acceptance_date=calc_date_params(
                backdate=backdate, setdate=setdate))
        with SessionScope(db):
            db.session.add(tou)
            db.session.add(privacy)
            db.session.add(consent)
            db.session.commit()

        # Invalidate org tree cache, in case orgs are added by other
        # tests.  W/o doing so, the new orgs aren't in the orgtree
        OrgTree.invalidate_cache()
    yield bless_with_basics



@pytest.fixture
def add_music_org():
    music_org = Organization(
        name="Michigan Urological Surgery Improvement Collaborative"
             " (MUSIC)")
    with SessionScope(db):
        db.session.add(music_org)
        db.session.commit()
    music_org = db.session.merge(music_org)


@pytest.fixture
def login(initialize_static, app, client, add_music_org):
    def login(
            user_id=TEST_USER_ID,
            oauth_info=None,
            follow_redirects=True
    ):
        initialize_static()

        app.config.from_object(TestConfig)

        if not oauth_info:
            oauth_info= {'user_id': user_id} 

        return client.get(
                'test/oauth',
                query_string=oauth_info,
                follow_redirects=follow_redirects
        )

    return login
    db.session.remove()
    db.engine.dispose()


@pytest.fixture
def local_login(client, initialize_static, add_music_org):
    def local_login(email, password, follow_redirects=True):
        initialize_static()
        url = url_for('user.login')
        return client.post(
            url,
            data={
                'email': email,
                'password': password,
            },
            follow_redirects=follow_redirects
        )
    return local_login


@pytest.fixture
def add_client(promote_user):
    def add_client():
        promote_user(role_name=ROLE.APPLICATION_DEVELOPER.value)
        client_id = 'test_client'
        client = Client(
                client_id=client_id, _redirect_uris='http://localhost',
                client_secret='tc_secret', user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(client)
            db.session.commit()
        return db.session.merge(client)
    return add_client


@pytest.fixture
def promote_user(initialize_static, test_user):
    def promote_user(user=None, role_name=None):
        initialize_static()

        """Bless a user with role needed for a test"""
        if not user:
            user = test_user
        user = db.session.merge(user)
        assert (role_name)
        role_id = db.session.query(Role.id).filter(
            Role.name == role_name).first()[0]
        with SessionScope(db):
            db.session.add(UserRoles(user_id=user.id, role_id=role_id))
            db.session.commit()
    return promote_user


@pytest.fixture
def assert_redirects(app):
    def assertRedirects(response, location, message=None):
        """
        Checks if response is an HTTP redirect to the
        given location.

        :param response: Flask response
        :param location: relative URL path to SERVER_NAME or an absolute URL
        """
        parts = urlparse(location)

        if parts.netloc:
            expected_location = location
        else:
            server_name = app.config.get('SERVER_NAME') or 'localhost'
            expected_location = urljoin("http://%s" % server_name, location)

        valid_status_codes = (301, 302, 303, 305, 307)
        valid_status_code_str = ', '.join(
                str(code) for code in valid_status_codes)
        not_redirect = "HTTP Status %s expected but got %d" % (
            valid_status_code_str, response.status_code)
        assert(
            response.status_code in valid_status_codes), (
                message or not_redirect)
        assert(response.location == expected_location), message
    return assertRedirects
