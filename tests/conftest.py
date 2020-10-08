# test plugin
# https://docs.pytest.org/en/latest/writing_plugins.html#conftest-py-plugins
from datetime import datetime
from glob import glob

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
from portal.models.clinical_constants import CC, add_static_concepts
from portal.models.codeable_concept import CodeableConcept
from portal.models.coding import Coding
from portal.models.identifier import Identifier
from portal.models.encounter import Encounter
from portal.models.intervention import add_static_interventions
from portal.models.organization import (
        Organization,
        OrgTree,
        add_static_organization
)
from portal.models.practitioner import Practitioner
from portal.models.procedure import Procedure
from portal.models.qb_timeline import invalidate_users_QBT
from portal.models.relationship import add_static_relationships
from portal.models.research_protocol import ResearchProtocol
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
from portal.system_uri import SNOMED, US_NPI
from tests import TEST_USER_ID


""" Include all fixtures found in nested fixtures dir as modules """
# The double load attempt is necessary given different IDE/tox/CI envs
pytest_plugins = [
    f"tests.{fixture.replace('/', '.')}"[:-3]
    for fixture in glob("fixtures/*.py")]
if not pytest_plugins:
    pytest_plugins = [
        f"{fixture.replace('/', '.')}"[:-3]
        for fixture in glob("tests/fixtures/*.py")]


def pytest_addoption(parser):
    parser.addoption(
        "--include-ui-testing",
        action="store_true",
        default=False,
        help="run selenium ui tests",
    )


@pytest.fixture(scope="function")
def shallow_org_tree():
    """Create shallow org tree for common test needs"""
    org_101 = Organization(id=101, name='101')
    org_102 = Organization(id=102, name='102')
    org_1001 = Organization(id=1001, name='1001', partOf_id=101)

    already_done = Organization.query.get(101)
    if not already_done:
        with SessionScope(db):
            [db.session.add(org) for org in (org_101, org_102, org_1001)]
            db.session.commit()

        # Invalidate as organizations were just added
        OrgTree.invalidate_cache()

    yield  # setup complete, teardown follows

    # After using this fixture, invalidate OrgTree so subsequent tests
    # don't find stale entries, namely dead references to the orgs created
    # above.
    OrgTree.invalidate_cache()


@pytest.fixture(scope="function")
def deepen_org_tree(shallow_org_tree):
    """Create deeper tree when test needs it"""
    org_l2 = Organization(id=1002, name='l2', partOf_id=102)
    org_l3_1 = Organization(id=10031, name='l3_1', partOf_id=1002)
    org_l3_2 = Organization(id=10032, name='l3_2', partOf_id=1002)
    with SessionScope(db):
        [db.session.add(org) for org in (org_l2, org_l3_1, org_l3_2)]
        db.session.commit()
    # As orgs were just added, make sure they're loaded on next OrgTree call
    OrgTree.invalidate_cache()

    yield

    # After using this fixture, invalidate OrgTree so subsequent tests
    # don't find stale entries, namely dead references to the orgs created
    # above.
    OrgTree.invalidate_cache()


@pytest.fixture
def prep_org_w_identifier():
    o = Organization(name='test org')
    i = Identifier(system=US_NPI, value='123-45')
    o.identifiers.append(i)
    with SessionScope(db):
        db.session.add(o)
        db.session.commit()
    o = db.session.merge(o)
    OrgTree().invalidate_cache()
    yield o

    OrgTree().invalidate_cache()


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


@pytest.fixture
def initialized_with_research_study(initialized_db):
    add_static_research_studies()
    db.session.commit()


@pytest.fixture
def initialized_with_research_protocol(initialized_with_research_study):
    rp = ResearchProtocol(name="test_rp", research_study_id=0)
    with SessionScope(db):
        db.session.add(rp)
        db.session.commit()
    return db.session.merge(rp)


@pytest.fixture
def initialize_static(initialized_db):
    add_static_concepts(only_quick=True)
    add_static_interventions()
    add_static_organization()
    add_static_relationships()
    add_static_research_studies()
    add_static_roles()
    db.session.commit()


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


@pytest.fixture(autouse=True)
def initialized_db(app):
    """Create database schema"""
    db.drop_all()
    db.create_all()

    yield

    cache.clear()
    db.session.remove()
    db.engine.dispose()
    db.drop_all()


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
    return test_user


@pytest.fixture
def initialized_patient(app, add_user, initialize_static, shallow_org_tree):
    """returns test patient with data necessary to avoid initial_queries"""
    TEST_USERNAME = 'test@example.com'
    FIRST_NAME = '✓'
    LAST_NAME = 'Last'
    IMAGE_URL = 'http://examle.com/photo.jpg'
    now = datetime.utcnow()
    test_user = add_user(
        username=TEST_USERNAME, first_name=FIRST_NAME,
        last_name=LAST_NAME, image_url=IMAGE_URL)
    test_user.birthdate = now
    test_user_id = test_user.id
    role_id = db.session.query(Role.id).filter(
        Role.name == 'patient').first()[0]
    with SessionScope(db):
        db.session.add(UserRoles(user_id=test_user_id, role_id=role_id))
        db.session.commit()

    org = Organization.query.filter(
        Organization.partOf_id.isnot(None)).first()
    test_user = db.session.merge(test_user)
    test_user.organizations.append(org)

    # Agree to Terms of Use and sign consent
    audit = Audit(user_id=test_user_id, subject_id=test_user_id)
    tou = ToU(
        audit=audit, agreement_url='http://not.really.org',
        type='website terms of use')
    subj_web = ToU(
        audit=audit, agreement_url='http://not.really.org',
        type='subject website consent')
    privacy = ToU(
        audit=audit, agreement_url='http://not.really.org',
        type='privacy policy')
    parent_org = OrgTree().find(org.id).top_level()
    options = (STAFF_EDITABLE_MASK | INCLUDE_IN_REPORTS_MASK |
               SEND_REMINDERS_MASK)
    add_static_research_studies()
    consent = UserConsent(
        user_id=test_user_id, organization_id=parent_org,
        options=options, audit=audit, agreement_url='http://fake.org',
        acceptance_date=now, research_study_id=0)

    for cc in CC.BIOPSY, CC.PCaDIAG, CC.PCaLocalized:
        test_user.save_observation(
            codeable_concept=cc, value_quantity=CC.TRUE_VALUE,
            audit=audit, status='preliminary', issued=now)

    with SessionScope(db):
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        procedure = Procedure(audit=audit)
        coding = Coding(
            system=SNOMED,
            code='999999999',
            display='Other primary treatment').add_if_not_found(True)
        code = CodeableConcept(codings=[coding]).add_if_not_found(True)
        enc = Encounter(
            status='planned',
            auth_method='url_authenticated',
            user_id=TEST_USER_ID, start_time=datetime.utcnow())
        db.session.add(enc)
        db.session.commit()
        enc = db.session.merge(enc)
        procedure.code = code
        procedure.user = db.session.merge(test_user)
        procedure.start_time = now
        procedure.encounter = enc
        db.session.add(procedure)
        db.session.commit()

    with SessionScope(db):
        db.session.add(tou)
        db.session.add(subj_web)
        db.session.add(privacy)
        db.session.add(consent)
        db.session.commit()

    yield test_user

    OrgTree.invalidate_cache()


@pytest.fixture
def initialized_patient_logged_in(client, initialized_patient):
    """Fixture to extend initialized patient to one logged in"""
    initialized_patient = db.session.merge(initialized_patient)
    oauth_info = {'user_id': initialized_patient.id}

    client.get(
        'test/oauth',
        query_string=oauth_info,
        follow_redirects=True
    )
    return initialized_patient


@pytest.fixture
def add_user(app, initialized_db):
    def add_user(
            username, first_name="James", last_name="Nguyen",
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
        invalidate_users_QBT(test_user.id, research_study_id='all')
        return test_user
    return add_user


@pytest.fixture
def service_user(initialize_static, test_user):
    sponsor = db.session.merge(test_user)
    service_user = sponsor.add_service_account()
    with SessionScope(db):
        db.session.add(service_user)
        db.session.commit()

    return db.session.merge(service_user)


@pytest.fixture
def bless_with_basics(test_user, promote_user, shallow_org_tree):
    user = None
    backdate = None
    setdate = None
    local_metastatic = None
    make_patient = True
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
    add_static_research_studies()
    options = (STAFF_EDITABLE_MASK | INCLUDE_IN_REPORTS_MASK |
               SEND_REMINDERS_MASK)
    consent = UserConsent(
        user_id=user_id, organization_id=parent_org,
        options=options, audit=audit, agreement_url='http://fake.org',
        acceptance_date=calc_date_params(
            backdate=backdate, setdate=setdate),
        research_study_id=0)
    with SessionScope(db):
        db.session.add(tou)
        db.session.add(privacy)
        db.session.add(consent)
        db.session.commit()

    # Invalidate org tree cache, in case orgs are added by other
    # tests.  W/o doing so, the new orgs aren't in the orgtree
    OrgTree.invalidate_cache()


@pytest.fixture
def bless_with_basics_no_patient_role(
        test_user, promote_user, shallow_org_tree):
    user = None
    backdate = None
    setdate = None
    local_metastatic = None
    make_patient = False
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
    add_static_research_studies()
    options = (STAFF_EDITABLE_MASK | INCLUDE_IN_REPORTS_MASK |
               SEND_REMINDERS_MASK)
    consent = UserConsent(
        user_id=user_id, organization_id=parent_org,
        options=options, audit=audit, agreement_url='http://fake.org',
        acceptance_date=calc_date_params(
            backdate=backdate, setdate=setdate),
        research_study_id=0)
    with SessionScope(db):
        db.session.add(tou)
        db.session.add(privacy)
        db.session.add(consent)
        db.session.commit()

    # Invalidate org tree cache, in case orgs are added by other
    # tests.  W/o doing so, the new orgs aren't in the orgtree
    OrgTree.invalidate_cache()


@pytest.fixture
def required_clinical_data():
    backdate = None
    setdate = None
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


@pytest.fixture
def add_practitioner():
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
    return add_practitioner


@pytest.fixture
def add_procedure(test_user):
    def add_procedure(code='367336001', display='Chemotherapy',
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
            procedure.user = db.session.merge(test_user)
            procedure.start_time = setdate or datetime.utcnow()
            procedure.end_time = datetime.utcnow()
            procedure.encounter = enc
            db.session.add(procedure)
            db.session.commit()
    return add_procedure


@pytest.fixture
def music_org():
    music_org = Organization(
        name="Michigan Urological Surgery Improvement Collaborative"
             " (MUSIC)")
    with SessionScope(db):
        db.session.add(music_org)
        db.session.commit()
    music_org = db.session.merge(music_org)
    yield music_org

    OrgTree.invalidate_cache()


@pytest.fixture
def login(initialize_static, app, client, music_org):
    def login(
            user_id=TEST_USER_ID,
            oauth_info=None,
            follow_redirects=True
    ):
        if not oauth_info:
            oauth_info = {'user_id': user_id}

        return client.get(
                'test/oauth',
                query_string=oauth_info,
                follow_redirects=follow_redirects
        )

    yield login
    db.session.remove()
    db.engine.dispose()


@pytest.fixture
def test_user_login(
        initialize_static, app, client,
        music_org, test_user):
    """Only use if the function requires user login before other tasks.
    login can be a location specific,
    calling login() manually if that is the case.
    """
    user_id = TEST_USER_ID,
    follow_redirects = True

    app.config.from_object(TestConfig)

    oauth_info = {'user_id': user_id}

    yield client.get(
            'test/oauth',
            query_string=oauth_info,
            follow_redirects=follow_redirects
    )

    db.session.remove()
    db.engine.dispose()


@pytest.fixture
def local_login(client, initialize_static, music_org):
    def local_login(email, password, follow_redirects=True):
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
def test_client(promote_user):
    promote_user(role_name=ROLE.APPLICATION_DEVELOPER.value)
    client_id = 'test_client'
    client = Client(
            client_id=client_id, _redirect_uris='http://localhost',
            client_secret='tc_secret', user_id=TEST_USER_ID)
    with SessionScope(db):
        db.session.add(client)
        db.session.commit()
    return db.session.merge(client)


@pytest.fixture
def system_user(add_user, promote_user):
    """create and return system user expected for some tasks """
    sysusername = '__system__'
    if not User.query.filter_by(username=sysusername).first():
        sys_user = add_user(sysusername, 'System', 'Admin')
    promote_user(sys_user, ROLE.ADMIN.value)
    return sys_user


@pytest.fixture
def promote_user(initialize_static, test_user):
    def promote_user(user=None, role_name=None):

        """Bless a user with role needed for a test"""
        if not user:
            user = test_user
        user = db.session.merge(user)
        assert role_name
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
