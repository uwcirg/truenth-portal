"""Unit test module for Intervention API"""
from flask_webtest import SessionScope
import json
from tests import TestCase, TEST_USER_ID
from tests.test_assessment_status import mock_qr, mock_questionnairebanks

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.fhir import CC
from portal.models.group import Group
from portal.models.identifier import Identifier
from portal.models.intervention import INTERVENTION, UserIntervention
from portal.models.intervention_strategies import AccessStrategy
from portal.models.message import EmailMessage
from portal.models.organization import Organization
from portal.models.role import ROLE
from portal.models.user import add_role
from portal.system_uri import DECISION_SUPPORT_GROUP, SNOMED

class TestIntervention(TestCase):

    def test_intervention_wrong_service_user(self):
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)

        data = {'user_id': TEST_USER_ID, 'access': 'granted'}
        rv = self.client.put('/api/intervention/sexual_recovery',
                content_type='application/json',
                data=json.dumps(data))
        self.assert401(rv)

    def test_intervention(self):
        client = self.add_client()
        client.intervention = INTERVENTION.SEXUAL_RECOVERY
        client.application_origins = 'http://safe.com'
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)

        data = {'user_id': TEST_USER_ID,
                'access': "granted",
                'card_html': "unique HTML set via API",
                'link_label': 'link magic',
                'link_url': 'http://safe.com',
                'status_text': 'status example',
                'staff_html': "unique HTML for /patients view"
               }

        rv = self.client.put('/api/intervention/sexual_recovery',
                content_type='application/json',
                data=json.dumps(data))
        self.assert200(rv)

        ui = UserIntervention.query.one()
        self.assertEquals(ui.user_id, data['user_id'])
        self.assertEquals(ui.access, data['access'])
        self.assertEquals(ui.card_html, data['card_html'])
        self.assertEquals(ui.link_label, data['link_label'])
        self.assertEquals(ui.link_url, data['link_url'])
        self.assertEquals(ui.status_text, data['status_text'])
        self.assertEquals(ui.staff_html, data['staff_html'])

    def test_intervention_bad_access(self):
        client = self.add_client()
        client.intervention = INTERVENTION.SEXUAL_RECOVERY
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)

        data = {'user_id': TEST_USER_ID,
                'access': 'enabled',
               }

        rv = self.client.put('/api/intervention/sexual_recovery',
                content_type='application/json',
                data=json.dumps(data))
        self.assert400(rv)

    def test_intervention_validation(self):
        client = self.add_client()
        client.intervention = INTERVENTION.SEXUAL_RECOVERY
        client.application_origins = 'http://safe.com'
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)

        data = {'user_id': TEST_USER_ID,
                'link_url': 'http://un-safe.com',
               }

        rv = self.client.put('/api/intervention/sexual_recovery',
                content_type='application/json',
                data=json.dumps(data))
        self.assert400(rv)

    def test_clinc_id(self):
        # Create several orgs with identifier
        org1 = Organization(name='org1')
        org2 = Organization(name='org2')
        org3 = Organization(name='org3')
        identifier = Identifier(value='pick me', system=DECISION_SUPPORT_GROUP)
        for org in (org1, org2, org3):
            org.identifiers.append(identifier)

        # Add access strategy to the care plan intervention
        cp = INTERVENTION.CARE_PLAN
        cp.public_access = False  # turn off public access to force strategy
        cp_id = cp.id

        with SessionScope(db):
            map(db.session.add, (org1, org2, org3))
            db.session.commit()

        org1, org2, org3 = map(db.session.merge, (org1, org2, org3))
        d = {'function': 'limit_by_clinic_w_id',
             'kwargs': [{'name': 'identifier_value',
                         'value': 'pick me'}]
            }
        strat = AccessStrategy(
            name="member of org with identifier",
            intervention_id = cp_id,
            function_details=json.dumps(d))

        with SessionScope(db):
            db.session.add(strat)
            db.session.commit()

        cp = INTERVENTION.CARE_PLAN
        user = db.session.merge(self.test_user)

        # Prior to associating user with any orgs, shouldn't have access
        self.assertFalse(cp.display_for_user(user).access)

        # Add association and test again
        user.organizations.append(org3)
        with SessionScope(db):
            db.session.commit()
        user, cp = map(db.session.merge, (user, cp))
        self.assertTrue(cp.display_for_user(user).access)

    def test_diag_stategy(self):
        """Test strategy for diagnosis"""
        # Add access strategies to the care plan intervention
        cp = INTERVENTION.CARE_PLAN
        cp.public_access = False  # turn off public access to force strategy
        cp_id = cp.id

        with SessionScope(db):
            d = {'function': 'observation_check',
                 'kwargs': [{'name': 'display', 'value':
                             CC.PCaDIAG.codings[0].display},
                            {'name': 'boolean_value', 'value': 'true'}]}
            strat = AccessStrategy(
                name="has PCa diagnosis",
                intervention_id = cp_id,
                function_details=json.dumps(d))
            db.session.add(strat)
            db.session.commit()
        cp = INTERVENTION.CARE_PLAN
        user = db.session.merge(self.test_user)

        # Prior to PCa dx, user shouldn't have access
        self.assertFalse(cp.display_for_user(user).access)

        # Bless the test user with PCa diagnosis
        user.save_constrained_observation(
            codeable_concept=CC.PCaDIAG, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID))
        with SessionScope(db):
            db.session.commit()
        user, cp = map(db.session.merge, (user, cp))

        self.assertTrue(cp.display_for_user(user).access)

    def test_no_tx(self):
        """Test strategy for not starting treatment"""
        # Add access strategies to the care plan intervention
        cp = INTERVENTION.CARE_PLAN
        cp.public_access = False  # turn off public access to force strategy
        cp_id = cp.id

        with SessionScope(db):
            d = {'function': 'tx_begun',
                 'kwargs': [{'name': 'boolean_value', 'value': 'false'}]}
            strat = AccessStrategy(
                name="has not stared treatment",
                intervention_id = cp_id,
                function_details=json.dumps(d))
            db.session.add(strat)
            db.session.commit()
        cp = INTERVENTION.CARE_PLAN
        user = db.session.merge(self.test_user)

        # Prior to declaring TX, user should have access
        self.assertTrue(cp.display_for_user(user).access)

        self.add_procedure(
            code='424313000', display='Started active surveillance')
        with SessionScope(db):
            db.session.commit()
        user, cp = map(db.session.merge, (user, cp))

        # Declaring they started a non TX proc, should still have access
        self.assertTrue(cp.display_for_user(user).access)

        self.add_procedure(
            code='26294005',
            display='Radical prostatectomy (nerve-sparing)',
            system=SNOMED)
        with SessionScope(db):
            db.session.commit()
        user, cp = map(db.session.merge, (user, cp))

        # Declaring they started a TX proc, should lose access
        self.assertFalse(cp.display_for_user(user).access)

    def test_exclusive_stategy(self):
        """Test exclusive intervention strategy"""
        user = self.test_user
        ds_p3p = INTERVENTION.DECISION_SUPPORT_P3P
        ds_wc = INTERVENTION.DECISION_SUPPORT_WISERCARE

        ds_p3p.public_access = False
        ds_wc.public_access = False

        with SessionScope(db):
            d = {'function': 'allow_if_not_in_intervention',
                 'kwargs': [{'name': 'intervention_name',
                            'value': ds_wc.name}]}
            strat = AccessStrategy(
                name="exclusive decision support strategy",
                intervention_id = ds_p3p.id,
                function_details=json.dumps(d))
            db.session.add(strat)
            db.session.commit()
        user, ds_p3p, ds_wc = map(db.session.merge, (user, ds_p3p, ds_wc))

        # Prior to associating user w/ decision support, the strategy
        # should give access to p3p
        self.assertTrue(ds_p3p.display_for_user(user).access)
        self.assertFalse(ds_wc.display_for_user(user).access)

        # Add user to wisercare, confirm it's the only w/ access

        ui = UserIntervention(user_id=user.id, intervention_id=ds_wc.id,
                              access='granted')
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()
        user, ds_p3p, ds_wc = map(db.session.merge, (user, ds_p3p, ds_wc))

        self.assertFalse(ds_p3p.display_for_user(user).access)
        self.assertTrue(ds_wc.display_for_user(user).access)

    def test_not_in_role_or_sr(self):
        user = self.test_user
        sm = INTERVENTION.SELF_MANAGEMENT
        sr = INTERVENTION.SEXUAL_RECOVERY

        sm.public_access = False
        sr.public_access = False
        d = {
             'function': 'combine_strategies',
             'kwargs': [
                 {'name': 'strategy_1',
                  'value': 'allow_if_not_in_intervention'},
                 {'name': 'strategy_1_kwargs',
                  'value': [{'name': 'intervention_name',
                             'value': INTERVENTION.SEXUAL_RECOVERY.name}]},
                 {'name': 'strategy_2',
                  'value': 'not_in_role_list'},
                 {'name': 'strategy_2_kwargs',
                  'value': [{'name': 'role_list',
                             'value': [ROLE.WRITE_ONLY,]}]}
                 ]
            }

        with SessionScope(db):
            strat = AccessStrategy(
                name="SELF_MANAGEMENT if not SR and not in WRITE_ONLY",
                intervention_id = sm.id,
                function_details=json.dumps(d))
            #print json.dumps(strat.as_json(), indent=2)
            db.session.add(strat)
            db.session.commit()
        user, sm, sr = map(db.session.merge, (user, sm, sr))

        # Prior to granting user WRITE_ONLY role, the strategy
        # should give access to p3p
        self.assertTrue(sm.display_for_user(user).access)

        # Add WRITE_ONLY to user's roles
        add_role(user, ROLE.WRITE_ONLY)
        with SessionScope(db):
            db.session.commit()
        user, sm, sr = map(db.session.merge, (user, sm, sr))
        self.assertFalse(sm.display_for_user(user).access)

        # Revert role change for next condition
        user.roles = []
        with SessionScope(db):
            db.session.commit()
        user, sm, sr = map(db.session.merge, (user, sm, sr))
        self.assertTrue(sm.display_for_user(user).access)

        # Grant user sr access, they should lose sm visibility
        ui = UserIntervention(
            user_id=user.id,
            intervention_id=INTERVENTION.SEXUAL_RECOVERY.id,
            access='granted')
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()
        user, sm, sr = map(db.session.merge, (user, sm, sr))
        self.assertFalse(sm.display_for_user(user).access)

    def test_in_role(self):
        user = self.test_user
        sm = INTERVENTION.SELF_MANAGEMENT
        sm.public_access = False
        d = {
             'function': 'in_role_list',
             'kwargs': [
                 {'name': 'role_list',
                  'value': [ROLE.PATIENT,]}]
            }

        with SessionScope(db):
            strat = AccessStrategy(
                name="SELF_MANAGEMENT if PATIENT",
                intervention_id = sm.id,
                function_details=json.dumps(d))
            db.session.add(strat)
            db.session.commit()
        user, sm = map(db.session.merge, (user, sm))

        # Prior to granting user PATIENT role, the strategy
        # should not give access to SM
        self.assertFalse(sm.display_for_user(user).access)

        # Add PATIENT to user's roles
        add_role(user, ROLE.PATIENT)
        with SessionScope(db):
            db.session.commit()
        user, sm = map(db.session.merge, (user, sm))
        self.assertTrue(sm.display_for_user(user).access)

    def test_card_html_update(self):
        """Test strategy with side effects - card_html update"""
        ae  = INTERVENTION.ASSESSMENT_ENGINE
        ae_id = ae.id
        self.bless_with_basics()

        # generate questionnaire banks and associate user with
        # metastatic organization
        mock_questionnairebanks()
        metastatic_org = Organization.query.filter_by(name='metastatic').one()
        self.test_user.organizations.append(metastatic_org)

        with SessionScope(db):
            d = {'function': 'update_card_html_on_completion',
                 'kwargs': []}
            strat = AccessStrategy(
                name="update assessment_engine card_html on completion",
                intervention_id = ae_id,
                function_details=json.dumps(d))
            db.session.add(strat)
            db.session.commit()
        user, ae = map(db.session.merge, (self.test_user, ae))

        # without completing an assessment, card_html should includ username
        self.assertTrue(
            user.display_name in ae.display_for_user(user).card_html)

        # Add a fake assessments and see a change
        mock_qr(user_id=TEST_USER_ID, instrument_id='eortc')
        mock_qr(user_id=TEST_USER_ID, instrument_id='ironmisc')
        mock_qr(user_id=TEST_USER_ID, instrument_id='factfpsi')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26')
        mock_qr(user_id=TEST_USER_ID, instrument_id='prems')
        mock_qr(user_id=TEST_USER_ID, instrument_id='irondemog')

        user, ae = map(db.session.merge, (self.test_user, ae))
        self.assertTrue(
            "Thank you" in ae.display_for_user(user).card_html)

    def test_strat_from_json(self):
        """Create access strategy from json"""
        d = {'name': 'unit test example',
             'description': 'a lovely way to test',
             'function_details': {
                 'function': 'allow_if_not_in_intervention',
                 'kwargs': [{'name': 'intervention_name',
                            'value': INTERVENTION.SELF_MANAGEMENT.name}]
             }
            }
        acc_strat = AccessStrategy.from_json(d)
        self.assertEquals(d['name'], acc_strat.name)
        self.assertEquals(d['function_details'],
                          json.loads(acc_strat.function_details))

    def test_strat_view(self):
        """Test strategy view functions"""
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        d = {'name': 'unit test example',
             'function_details': {
                 'function': 'allow_if_not_in_intervention',
                 'kwargs': [{'name': 'intervention_name',
                            'value': INTERVENTION.SELF_MANAGEMENT.name}]
             }
            }
        rv = self.client.post('/api/intervention/sexual_recovery/access_rule',
                content_type='application/json',
                data=json.dumps(d))
        self.assert200(rv)

        # fetch it back and compare
        rv = self.client.get('/api/intervention/sexual_recovery/access_rule')
        self.assert200(rv)
        data = json.loads(rv.data)
        self.assertEqual(len(data['rules']), 1)
        self.assertEqual(d['name'], data['rules'][0]['name'])
        self.assertEqual(d['function_details'],
                         data['rules'][0]['function_details'])

    def test_strat_dup_rank(self):
        """Rank must be unique"""
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        d = {'name': 'unit test example',
             'rank': 1,
             'function_details': {
                 'function': 'allow_if_not_in_intervention',
                 'kwargs': [{'name': 'intervention_name',
                            'value': INTERVENTION.SELF_MANAGEMENT.name}]
             }
            }
        rv = self.client.post('/api/intervention/sexual_recovery/access_rule',
                content_type='application/json',
                data=json.dumps(d))
        self.assert200(rv)
        d = {'name': 'unit test same rank example',
             'rank': 1,
             'description': 'should not take with same rank',
             'function_details': {
                 'function': 'allow_if_not_in_intervention',
                 'kwargs': [{'name': 'intervention_name',
                            'value': INTERVENTION.SELF_MANAGEMENT.name}]
             }
            }
        rv = self.client.post('/api/intervention/sexual_recovery/access_rule',
                content_type='application/json',
                data=json.dumps(d))
        self.assert400(rv)

    def test_and_strats(self):
        # Create a logical 'and' with multiple strategies

        ds_p3p = INTERVENTION.DECISION_SUPPORT_P3P
        ds_p3p.public_access = False
        user = self.test_user
        identifier = Identifier(
            value='decision_support_p3p', system=DECISION_SUPPORT_GROUP)
        uw = Organization(name='UW Medicine (University of Washington)')
        uw.identifiers.append(identifier)
        INTERVENTION.SEXUAL_RECOVERY.public_access = False
        with SessionScope(db):
            db.session.add(uw)
            db.session.commit()
        user, uw = map(db.session.merge, (user, uw))
        uw_child = Organization(name='UW clinic', partOf_id=uw.id)
        with SessionScope(db):
            db.session.add(uw_child)
            db.session.commit()
        user, uw, uw_child = map(db.session.merge, (user, uw, uw_child))

        d = {'name': 'not in SR _and_ in clinc UW',
             'function': 'combine_strategies',
             'kwargs': [
                 {'name': 'strategy_1',
                  'value': 'allow_if_not_in_intervention'},
                 {'name': 'strategy_1_kwargs',
                  'value': [{'name': 'intervention_name',
                             'value': INTERVENTION.SEXUAL_RECOVERY.name}]},
                 {'name': 'strategy_2',
                  'value': 'limit_by_clinic_w_id'},
                 {'name': 'strategy_2_kwargs',
                  'value': [{'name': 'identifier_value',
                             'value': 'decision_support_p3p'}]}
                 ]
            }
        with SessionScope(db):
            strat = AccessStrategy(
                name=d['name'],
                intervention_id = INTERVENTION.DECISION_SUPPORT_P3P.id,
                function_details=json.dumps(d))
            db.session.add(strat)
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))

        # first strat true, second false.  therfore, should be False
        self.assertFalse(ds_p3p.display_for_user(user).access)

        # Add the child organization to the user, which should be included
        # due to default behavior of limit_by_clinic_w_id
        user.organizations.append(uw_child)
        with SessionScope(db):
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))
        # first strat true, second true.  therfore, should be True
        self.assertTrue(ds_p3p.display_for_user(user).access)

        ui = UserIntervention(
            user_id=user.id,
            intervention_id=INTERVENTION.SEXUAL_RECOVERY.id,
            access='granted')
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))

        # first strat true, second false.  AND should be false
        self.assertFalse(ds_p3p.display_for_user(user).access)

    def test_p3p_conditions(self):
        # Test the list of conditions expected for p3p
        ds_p3p = INTERVENTION.DECISION_SUPPORT_P3P
        ds_p3p.public_access = False
        user = self.test_user
        p3p_identifier = Identifier(
            value='decision_support_p3p', system=DECISION_SUPPORT_GROUP)
        wc_identifier = Identifier(
            value='decision_support_wisercare', system=DECISION_SUPPORT_GROUP)
        ucsf = Organization(name='UCSF Medical Center')
        uw = Organization(
            name='UW Medicine (University of Washington)')
        ucsf.identifiers.append(wc_identifier)
        uw.identifiers.append(p3p_identifier)
        with SessionScope(db):
            db.session.add(ucsf)
            db.session.add(uw)
            db.session.commit()
        user.organizations.append(ucsf)
        user.organizations.append(uw)
        INTERVENTION.SEXUAL_RECOVERY.public_access = False
        with SessionScope(db):
            db.session.commit()
        ucsf, user, uw = map(db.session.merge, (ucsf, user, uw))

        # Full logic from story #127433167
        description = ("[strategy_1: (user NOT IN sexual_recovery)] "
            "AND [strategy_2 <a nested combined strategy>: "
            "((user NOT IN list of clinics (including UCSF)) OR "
            "(user IN list of clinics including UCSF and UW))] "
            "AND [strategy_3: (user has NOT started TX)] "
            "AND [strategy_4: (user does NOT have PCaMETASTASIZE)]")

        d = {'function': 'combine_strategies',
             'kwargs': [
                 # Not in SR (strat 1)
                 {'name': 'strategy_1',
                  'value': 'allow_if_not_in_intervention'},
                 {'name': 'strategy_1_kwargs',
                  'value': [{'name': 'intervention_name',
                             'value': INTERVENTION.SEXUAL_RECOVERY.name}]},
                 # Not in clinic list (UCSF,) OR (In Clinic UW and UCSF) (#2)
                 {'name': 'strategy_2',
                  'value': 'combine_strategies'},
                 {'name': 'strategy_2_kwargs',
                  'value': [
                      {'name': 'combinator',
                       'value': 'any'},  # makes this combination an 'OR'
                      {'name': 'strategy_1',
                       'value': 'not_in_clinic_w_id'},
                      {'name': 'strategy_1_kwargs',
                       'value': [{'name': 'identifier_value',
                                  'value': 'decision_support_wisercare'}]},
                      {'name': 'strategy_2',
                       'value': 'limit_by_clinic_w_id'},
                      {'name': 'strategy_2_kwargs',
                       'value': [{'name': 'identifier_value',
                                  'value': 'decision_support_p3p'}]},
                  ]},
                 # Not Started TX (strat 3)
                 {'name': 'strategy_3',
                  'value': 'tx_begun'},
                 {'name': 'strategy_3_kwargs',
                  'value': [{'name': 'boolean_value', 'value': 'false'}]},
                 # Has Localized PCa (strat 4)
                 {'name': 'strategy_4',
                  'value': 'observation_check'},
                 {'name': 'strategy_4_kwargs',
                  'value': [{'name': 'display',
                             'value': CC.PCaLocalized.codings[0].display},
                            {'name': 'boolean_value', 'value': 'true'}]},
                 ]
            }
        with SessionScope(db):
            strat = AccessStrategy(
                name='P3P Access Conditions',
                description=description,
                intervention_id=INTERVENTION.DECISION_SUPPORT_P3P.id,
                function_details=json.dumps(d))
            #print json.dumps(strat.as_json(), indent=2)
            db.session.add(strat)
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))

        # only first two strats true so far, therfore, should be False
        self.assertFalse(ds_p3p.display_for_user(user).access)

        self.add_procedure(
            code='424313000', display='Started active surveillance')
        user.save_constrained_observation(
            codeable_concept=CC.PCaLocalized, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID))
        with SessionScope(db):
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))

        # All conditions now met, should have access
        self.assertTrue(ds_p3p.display_for_user(user).access)

        # Remove all clinics, should still have access
        user.organizations = []
        with SessionScope(db):
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))
        self.assertEquals(user.organizations.count(), 0)
        self.assertTrue(ds_p3p.display_for_user(user).access)

    def test_eproms_p3p_conditions(self):
        # Test the list of conditions expected for p3p on eproms
        # very similar to truenth p3p, plus ! role write_only
        ds_p3p = INTERVENTION.DECISION_SUPPORT_P3P
        ds_p3p.public_access = False
        user = self.test_user
        p3p_identifier = Identifier(
            value='decision_support_p3p', system=DECISION_SUPPORT_GROUP)
        wc_identifier = Identifier(
            value='decision_support_wisercare', system=DECISION_SUPPORT_GROUP)
        ucsf = Organization(name='UCSF Medical Center')
        uw = Organization(
            name='UW Medicine (University of Washington)')
        ucsf.identifiers.append(wc_identifier)
        uw.identifiers.append(p3p_identifier)
        with SessionScope(db):
            db.session.add(ucsf)
            db.session.add(uw)
            db.session.commit()
        user.organizations.append(ucsf)
        user.organizations.append(uw)
        INTERVENTION.SEXUAL_RECOVERY.public_access = False
        with SessionScope(db):
            db.session.commit()
        ucsf, user, uw = map(db.session.merge, (ucsf, user, uw))

        # Full logic from story #127433167
        description = ("[strategy_1: (user NOT IN sexual_recovery)] "
            "AND [strategy_2 <a nested combined strategy>: "
            "((user NOT IN list of clinics (including UCSF)) OR "
            "(user IN list of clinics including UCSF and UW))] "
            "AND [strategy_3: (user has NOT started TX)] "
            "AND [strategy_4: (user does NOT have PCaMETASTASIZE)] "
            "AND [startegy_5: (user does NOT have roll WRITE_ONLY)]")

        d = {'function': 'combine_strategies',
             'kwargs': [
                 # Not in SR (strat 1)
                 {'name': 'strategy_1',
                  'value': 'allow_if_not_in_intervention'},
                 {'name': 'strategy_1_kwargs',
                  'value': [{'name': 'intervention_name',
                             'value': INTERVENTION.SEXUAL_RECOVERY.name}]},
                 # Not in clinic list (UCSF,) OR (In Clinic UW and UCSF) (#2)
                 {'name': 'strategy_2',
                  'value': 'combine_strategies'},
                 {'name': 'strategy_2_kwargs',
                  'value': [
                      {'name': 'combinator',
                       'value': 'any'},  # makes this combination an 'OR'
                      {'name': 'strategy_1',
                       'value': 'not_in_clinic_w_id'},
                      {'name': 'strategy_1_kwargs',
                       'value': [{'name': 'identifier_value',
                                  'value': 'decision_support_wisercare'}]},
                     {'name': 'strategy_2',
                      'value': 'combine_strategies'},
                     {'name': 'strategy_2_kwargs',
                      'value': [
                          {'name': 'strategy_1',
                           'value': 'limit_by_clinic_w_id'},
                          {'name': 'strategy_1_kwargs',
                           'value': [{'name': 'identifier_value',
                                      'value': 'decision_support_wisercare'}]},
                          {'name': 'strategy_2',
                           'value': 'limit_by_clinic_w_id'},
                          {'name': 'strategy_2_kwargs',
                           'value': [{'name': 'identifier_value',
                                      'value': 'decision_support_p3p'}]},
                      ]},
                  ]},
                 # Not Started TX (strat 3)
                 {'name': 'strategy_3',
                  'value': 'tx_begun'},
                 {'name': 'strategy_3_kwargs',
                  'value': [{'name': 'boolean_value', 'value': 'false'}]},
                 # Has Localized PCa (strat 4)
                 {'name': 'strategy_4',
                  'value': 'observation_check'},
                 {'name': 'strategy_4_kwargs',
                  'value': [{'name': 'display',
                             'value': CC.PCaLocalized.codings[0].display},
                            {'name': 'boolean_value', 'value': 'true'}]},
                 # Does NOT have roll WRITE_ONLY (strat 5)
                 {'name': 'strategy_5',
                  'value': 'not_in_role_list'},
                 {'name': 'strategy_5_kwargs',
                  'value': [{'name': 'role_list',
                             'value': [ROLE.WRITE_ONLY,]}]}
                 ]
            }
        with SessionScope(db):
            strat = AccessStrategy(
                name='P3P Access Conditions',
                description=description,
                intervention_id=INTERVENTION.DECISION_SUPPORT_P3P.id,
                function_details=json.dumps(d))
            #print json.dumps(strat.as_json(), indent=2)
            db.session.add(strat)
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))

        # only first two strats true so far, therfore, should be False
        self.assertFalse(ds_p3p.display_for_user(user).access)

        self.add_procedure(
            code='424313000', display='Started active surveillance')
        user.save_constrained_observation(
            codeable_concept=CC.PCaLocalized, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID))
        with SessionScope(db):
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))

        # All conditions now met, should have access
        self.assertTrue(ds_p3p.display_for_user(user).access)

        # Remove all clinics, should still have access
        user.organizations = []
        with SessionScope(db):
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))
        self.assertEquals(user.organizations.count(), 0)
        self.assertTrue(ds_p3p.display_for_user(user).access)

        # Finally, add the WRITE_ONLY group and it should disappear
        add_role(user, ROLE.WRITE_ONLY)
        with SessionScope(db):
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))
        self.assertFalse(ds_p3p.display_for_user(user).access)

    def test_get_empty_user_intervention(self):
        # Get on user w/o user_intervention
        self.login()
        rv = self.client.get('/api/intervention/{i}/user/{u}'.format(
            i=INTERVENTION.SELF_MANAGEMENT.name, u=TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(len(rv.json.keys()), 1)
        self.assertEquals(rv.json['user_id'], TEST_USER_ID)

    def test_get_user_intervention(self):
        intervention_id = INTERVENTION.SEXUAL_RECOVERY.id
        ui = UserIntervention(intervention_id=intervention_id,
                              user_id=TEST_USER_ID,
                              access='granted',
                              card_html='custom ch',
                              link_label='link magic',
                              link_url='http://example.com',
                              status_text='status example',
                              staff_html='custom ph')
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()

        self.login()
        rv = self.client.get('/api/intervention/{i}/user/{u}'.format(
            i=INTERVENTION.SEXUAL_RECOVERY.name, u=TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(len(rv.json.keys()), 7)
        self.assertEquals(rv.json['user_id'], TEST_USER_ID)
        self.assertEquals(rv.json['access'], 'granted')
        self.assertEquals(rv.json['card_html'], "custom ch")
        self.assertEquals(rv.json['link_label'], "link magic")
        self.assertEquals(rv.json['link_url'], "http://example.com")
        self.assertEquals(rv.json['status_text'], "status example")
        self.assertEquals(rv.json['staff_html'], "custom ph")


    def test_communicate(self):
        email_group = Group(name='test_email')
        foo = self.add_user(username='foo@example.com')
        boo = self.add_user(username='boo@example.com')
        foo, boo = map(db.session.merge, (foo, boo))
        foo.groups.append(email_group)
        boo.groups.append(email_group)
        data = {'protocol': 'email',
                'group_name': 'test_email',
                'subject': "Just a test, ignore",
                'message':
                    'Review results at <a href="http://www.example.com">here</a>'
               }
        self.login()
        rv = self.client.post('/api/intervention/{}/communicate'.format(
                INTERVENTION.DECISION_SUPPORT_P3P.name),
                content_type='application/json',
                data=json.dumps(data))
        self.assert200(rv)
        self.assertEquals(rv.json['message'], 'sent')

        message = EmailMessage.query.one()
        set1 = set((foo.email, boo.email))
        set2 = set(message.recipients.split())
        self.assertEquals(set1, set2)
