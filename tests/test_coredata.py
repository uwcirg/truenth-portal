"""Coredata tests"""
from __future__ import unicode_literals  # isort:skip

from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.coredata import Coredata, configure_coredata
from portal.models.organization import Organization
from portal.models.role import ROLE
from tests import TEST_USER_ID, TestCase

TRUENTH = 'TrueNTH'
EPROMS = 'ePROMs'
PRIVACY = 'privacy_policy'
WEB_TOU = 'website_terms_of_use'
SUBJ_CONSENT = 'subject_website_consent'
STORED_FORM = 'stored_website_consent_form'


class TestCoredata(TestCase):

    def config_as(self, system, **kwargs):
        """Set REQUIRED_CORE_DATA to match system under test"""
        # Ideally this would be read directly from the respective
        # site_persistence repos...
        if system == TRUENTH:
            self.app.config['REQUIRED_CORE_DATA'] = [
                'name', 'dob', 'role', 'org', 'clinical', 'localized',
                'treatment', 'race', 'ethnicity', 'indigenous',
                'website_terms_of_use'
            ]
        elif system == EPROMS:
            self.app.config['REQUIRED_CORE_DATA'] = [
                'org', 'website_terms_of_use', 'subject_website_consent',
                'stored_website_consent_form', 'privacy_policy', 'race',
                'ethnicity']
        else:
            raise ValueError("unsupported system {}".format(system))

        for k, v in kwargs.items():
            self.app.config[k] = v

        # reset coredata singleton, which already read in config
        # during bootstrap
        Coredata.reset()
        configure_coredata(self.app)

    def test_registry(self):
        assert len(Coredata()._registered) > 1

    def test_partner(self):
        """Partner doesn't need dx etc., set min and check pass"""
        self.config_as(TRUENTH)
        self.bless_with_basics(make_patient=False)
        self.promote_user(role_name=ROLE.PARTNER.value)
        self.test_user = db.session.merge(self.test_user)
        assert Coredata().initial_obtained(self.test_user)

    def test_patient(self):
        """Patient has additional requirements"""
        self.config_as(TRUENTH)
        self.bless_with_basics()
        self.test_user = db.session.merge(self.test_user)
        # Prior to adding clinical data, should return false
        Coredata()
        assert not Coredata().initial_obtained(self.test_user)

        self.login()
        self.add_required_clinical_data()
        self.add_procedure(code='118877007', display='Procedure on prostate')
        with SessionScope(db):
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        # should leave only indigenous, race and ethnicity as options
        # and nothing required
        assert Coredata().initial_obtained(self.test_user)
        expect = {'race', 'ethnicity', 'indigenous'}
        found = set(Coredata().optional(self.test_user))
        assert found == expect

    def test_still_needed(self):
        """Query for list of missing datapoints in legible format"""
        self.config_as(TRUENTH)
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.test_user = db.session.merge(self.test_user)

        needed = [i['field'] for i in Coredata().still_needed(self.test_user)]
        assert len(needed) > 1
        assert 'dob' in needed
        assert 'website_terms_of_use' in needed
        assert 'clinical' in needed
        assert 'treatment' in needed
        assert 'org' in needed

        # needed should match required (minus 'name', 'role')
        required = Coredata().required(self.test_user)
        assert set(required) - set(needed) == {'name', 'role'}

    def test_eproms_staff(self):
        """Eproms staff: privacy policy and website terms of use"""
        self.config_as(EPROMS)
        self.promote_user(role_name=ROLE.STAFF.value)
        self.test_user = db.session.merge(self.test_user)

        needed = [i['field'] for i in Coredata().still_needed(self.test_user)]
        assert PRIVACY in needed
        assert WEB_TOU in needed
        assert SUBJ_CONSENT not in needed
        assert STORED_FORM not in needed

    def test_eproms_patient(self):
        """Eproms patient: all ToU but stored form"""
        self.config_as(EPROMS)
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.test_user = db.session.merge(self.test_user)

        needed = [i['field'] for i in Coredata().still_needed(self.test_user)]
        assert PRIVACY in needed
        assert WEB_TOU in needed
        assert SUBJ_CONSENT in needed
        assert STORED_FORM not in needed

    def test_enter_manually_interview_assisted(self):
        "interview: subject_website_consent and stored_web_consent_form"
        self.config_as(EPROMS)
        self.promote_user(role_name=ROLE.STAFF.value)
        patient = self.add_user('patient')
        self.promote_user(patient, role_name=ROLE.PATIENT.value)
        self.test_user, patient = map(
            db.session.merge, (self.test_user, patient))

        needed = [i['field'] for i in Coredata().still_needed(
            patient, entry_method='interview assisted')]
        assert PRIVACY not in needed
        assert WEB_TOU not in needed
        assert SUBJ_CONSENT in needed
        assert STORED_FORM in needed

    def test_enter_manually_paper(self):
        "paper: subject_website_consent"
        self.config_as(EPROMS)
        self.promote_user(role_name=ROLE.STAFF.value)
        patient = self.add_user('patient')
        self.promote_user(patient, role_name=ROLE.PATIENT.value)
        self.test_user, patient = map(
            db.session.merge, (self.test_user, patient))

        needed = [i['field'] for i in Coredata().still_needed(
            patient, entry_method='paper')]
        assert PRIVACY not in needed
        assert WEB_TOU not in needed
        assert SUBJ_CONSENT in needed
        assert STORED_FORM not in needed

    def test_music_exception(self):
        "For patients with music org, the terms get special handling"
        music_org = Organization(
            name="Michigan Urological Surgery Improvement Collaborative"
                 " (MUSIC)")
        with SessionScope(db):
            db.session.add(music_org)
            db.session.commit()
        music_org = db.session.merge(music_org)

        self.config_as(
            system=TRUENTH, ACCEPT_TERMS_ON_NEXT_ORG=music_org.name)
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(music_org)
        self.promote_user(role_name=ROLE.PATIENT.value)

        user = db.session.merge(self.test_user)
        needed = Coredata().still_needed(user)
        assert ({'field': WEB_TOU, 'collection_method': "ACCEPT_ON_NEXT"}
                in needed)

        self.login()
        resp = self.client.get(
            '/api/coredata/user/{}/still_needed'.format(TEST_USER_ID))
        assert resp.status_code == 200
        passed = False
        for entry in resp.json['still_needed']:
            if entry['field'] == WEB_TOU:
                assert entry['collection_method'] == 'ACCEPT_ON_NEXT'
                passed = True
        assert passed
