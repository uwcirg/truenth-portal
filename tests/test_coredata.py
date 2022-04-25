"""Coredata tests"""

from flask_webtest import SessionScope
import pytest

from portal.extensions import db
from portal.models.coredata import Coredata, configure_coredata
from portal.models.role import ROLE
from tests import TEST_USER_ID

TRUENTH = 'TrueNTH'
EPROMS = 'ePROMs'
PRIVACY = 'privacy_policy'
WEB_TOU = 'website_terms_of_use'
SUBJ_CONSENT = 'subject_website_consent'
STORED_FORM = 'stored_website_consent_form'


@pytest.fixture
def prostate_procedure(add_procedure):
    add_procedure('118877007', 'Procedure on prostate')


def config_as(app, system, **kwargs):
    """Set REQUIRED_CORE_DATA to match system under test"""
    # Ideally this would be read directly from the respective
    # site_persistence repos...
    if system == TRUENTH:
        app.config['REQUIRED_CORE_DATA'] = [
            'name', 'dob', 'role', 'org', 'clinical', 'localized',
            'treatment', 'race', 'ethnicity', 'indigenous',
            'website_terms_of_use'
        ]
    elif system == EPROMS:
        app.config['REQUIRED_CORE_DATA'] = [
            'org', 'website_terms_of_use', 'subject_website_consent',
            'stored_website_consent_form', 'privacy_policy', 'race',
            'ethnicity']
    else:
        raise ValueError("unsupported system {}".format(system))

    for k, v in kwargs.items():
        app.config[k] = v

    # reset coredata singleton, which already read in config
    # during bootstrap
    Coredata.reset()
    configure_coredata(app)


def test_registry():
    assert len(Coredata()._registered) > 1


def test_partner(
        app, bless_with_basics_no_patient_role, promote_user,
        test_user, initialized_db):
    """Partner doesn't need dx etc., set min and check pass"""
    config_as(app, TRUENTH)
    promote_user(role_name=ROLE.PARTNER.value)
    test_user = db.session.merge(test_user)
    assert Coredata().initial_obtained(test_user)


def test_patient_without_clinical_data(
        app, bless_with_basics, test_user, initialized_db):
    config_as(app, TRUENTH)
    # Prior to adding clinical data, should return false
    Coredata()
    test_user = db.session.merge(test_user)
    assert not Coredata().initial_obtained(test_user)


def test_patient_with_clinical_data(
        app, bless_with_basics, test_user,
        test_user_login, required_clinical_data,
        prostate_procedure, initialized_db):
    """Patient has additional requirements"""
    # related to whether patient has received treatment question
    with SessionScope(db):
        db.session.commit()
    test_user = db.session.merge(test_user)
    # should leave only indigenous, race and ethnicity as options
    # and nothing required
    assert Coredata().initial_obtained(test_user)
    expect = {'race', 'ethnicity', 'indigenous'}
    found = set(Coredata().optional(test_user))
    assert found == expect


def test_still_needed(
        app, patient_user,
        music_org, initialized_db):
    """Query for list of missing datapoints in legible format"""
    config_as(app, TRUENTH)
    patient_user = db.session.merge(patient_user)

    needed = [i['field'] for i in Coredata().still_needed(patient_user)]
    assert len(needed) > 1
    assert 'dob' in needed
    assert 'website_terms_of_use' in needed
    assert 'clinical' in needed
    assert 'treatment' in needed
    assert 'org' in needed

    # needed should match required (minus 'name', 'role')
    required = Coredata().required(patient_user)
    assert set(required) - set(needed) == {'name', 'role'}


def test_eproms_staff(
        app, staff_user,
        music_org, initialized_db):
    """Eproms staff: privacy policy and website terms of use"""
    config_as(app, EPROMS)
    test_user = db.session.merge(staff_user)

    needed = [i['field'] for i in Coredata().still_needed(test_user)]
    assert PRIVACY in needed
    assert WEB_TOU in needed
    assert SUBJ_CONSENT not in needed
    assert STORED_FORM not in needed


def test_eproms_patient(
        app, patient_user,
        music_org, initialized_db):
    """Eproms patient: all ToU but stored form"""
    config_as(app, EPROMS)
    test_user = db.session.merge(patient_user)

    needed = [i['field'] for i in Coredata().still_needed(test_user)]
    assert PRIVACY in needed
    assert WEB_TOU in needed
    assert SUBJ_CONSENT in needed
    assert STORED_FORM not in needed


def test_enter_manually_interview_assisted(
        app, staff_user, patient_user,
        music_org, initialized_db):
    "interview: subject_website_consent and stored_web_consent_form"
    config_as(app, EPROMS)
    test_user, patient = map(
        db.session.merge, (staff_user, patient_user))

    needed = [i['field'] for i in Coredata().still_needed(
        patient, entry_method='interview assisted')]
    assert PRIVACY not in needed
    assert WEB_TOU not in needed
    assert SUBJ_CONSENT in needed
    assert STORED_FORM in needed


def test_enter_manually_paper(
        app, staff_user, patient_user,
        music_org, initialized_db):
    "paper: subject_website_consent"
    config_as(app, EPROMS)
    test_user, patient = map(
        db.session.merge, (staff_user, patient_user))

    needed = [i['field'] for i in Coredata().still_needed(
        patient, entry_method='paper')]
    assert PRIVACY not in needed
    assert WEB_TOU not in needed
    assert SUBJ_CONSENT in needed
    assert STORED_FORM not in needed


def test_music_exception(
        app, patient_user, client,
        login, music_org, initialized_db):
    config_as(
        app, system=TRUENTH, ACCEPT_TERMS_ON_NEXT_ORG=music_org.name)
    test_user = db.session.merge(patient_user)
    test_user.organizations.append(music_org)

    user = db.session.merge(test_user)
    needed = Coredata().still_needed(user)
    assert ({'field': WEB_TOU, 'collection_method': "ACCEPT_ON_NEXT"}
            in needed)

    login()
    resp = client.get(
        '/api/coredata/user/{}/still_needed'.format(TEST_USER_ID))
    assert resp.status_code == 200
    passed = False
    for entry in resp.json['still_needed']:
        if entry['field'] == WEB_TOU:
            assert entry['collection_method'] == 'ACCEPT_ON_NEXT'
            passed = True
    assert passed
