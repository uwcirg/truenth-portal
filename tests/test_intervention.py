"""Unit test module for Intervention API"""
from flask_webtest import SessionScope
import json
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.fhir import CC
from portal.models.group import Group
from portal.models.intervention import INTERVENTION, UserIntervention
from portal.models.intervention_strategies import AccessStrategy
from portal.models.message import EmailMessage
from portal.models.organization import Organization
from portal.models.role import ROLE

class TestIntervention(TestCase):

    def test_intervention_wrong_service_user(self):
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)

        data = {'user_id': TEST_USER_ID, 'access': 'granted'}
        rv = self.app.put('/api/intervention/sexual_recovery',
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
                'provider_html': "unique HTML for /patients view"
               }

        rv = self.app.put('/api/intervention/sexual_recovery',
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
        self.assertEquals(ui.provider_html, data['provider_html'])

    def test_intervention_bad_access(self):
        client = self.add_client()
        client.intervention = INTERVENTION.SEXUAL_RECOVERY
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)

        data = {'user_id': TEST_USER_ID,
                'access': 'enabled',
               }

        rv = self.app.put('/api/intervention/sexual_recovery',
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

        rv = self.app.put('/api/intervention/sexual_recovery',
                content_type='application/json',
                data=json.dumps(data))
        self.assert400(rv)

    def test_multi_strategy(self):
        """Add strategy to limit users to any of several clinics"""
        # Create several orgs - one of which the user is associated with
        org1 = Organization(name='org1')
        org2 = Organization(name='org2')
        org3 = Organization(name='org3')

        # Add access strategies to the care plan intervention
        cp = INTERVENTION.CARE_PLAN
        cp.public_access = False  # turn off public access to force strategy
        cp_id = cp.id

        with SessionScope(db):
            map(db.session.add, (org1, org2, org3))
            db.session.commit()

        org1, org2, org3 = map(db.session.merge, (org1, org2, org3))
        d = {'function': 'limit_by_clinic_list',
             'kwargs': [{'name': 'org_list',
                         'value': [o.name for o in (org1, org2, org3)]},
                        {'name': 'combinator',
                         'value': 'any'}]
            }
        strat = AccessStrategy(
            name="member of org list",
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
            audit=Audit(user_id=TEST_USER_ID))
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
            d = {'function': 'observation_check',
                 'kwargs': [{'name': 'display', 'value':
                             CC.TX.codings[0].display},
                            {'name': 'boolean_value', 'value': 'false'}]}
            strat = AccessStrategy(
                name="has not stared treatment",
                intervention_id = cp_id,
                function_details=json.dumps(d))
            db.session.add(strat)
            db.session.commit()
        cp = INTERVENTION.CARE_PLAN
        user = db.session.merge(self.test_user)

        # Prior to declaring TX, user shouldn't have access
        self.assertFalse(cp.display_for_user(user).access)

        user.save_constrained_observation(
            codeable_concept=CC.TX, value_quantity=CC.FALSE_VALUE,
            audit=Audit(user_id=TEST_USER_ID))
        with SessionScope(db):
            db.session.commit()
        user, cp = map(db.session.merge, (user, cp))

        # Declaring they started TX, should grant access
        self.assertTrue(cp.display_for_user(user).access)

        # Say user starts treatment, should lose access
        user.save_constrained_observation(
            codeable_concept=CC.TX, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID))
        with SessionScope(db):
            db.session.commit()
        user, cp = map(db.session.merge, (user, cp))

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

    def test_side_effects(self):
        """Test strategy with side effects"""
        ae  = INTERVENTION.ASSESSMENT_ENGINE
        ae_id = ae.id

        with SessionScope(db):
            d = {'function': 'update_link_url',
                 'kwargs': [{'name': 'intervention_name', 'value': ae.name},
                            {'name': 'link_url', 'value':
                             'http://different.org'}]}
            strat = AccessStrategy(
                name="fix assessment_engine link_url",
                intervention_id = ae_id,
                function_details=json.dumps(d))
            db.session.add(strat)
            db.session.commit()
        user, ae = map(db.session.merge, (self.test_user, ae))

        # We should now see the updated link_url for this user
        self.assertEquals(ae.display_for_user(user).link_url,
                          'http://different.org')

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
        rv = self.app.post('/api/intervention/sexual_recovery/access_rule',
                content_type='application/json',
                data=json.dumps(d))
        self.assert200(rv)

        # fetch it back and compare
        rv = self.app.get('/api/intervention/sexual_recovery/access_rule')
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
        rv = self.app.post('/api/intervention/sexual_recovery/access_rule',
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
        rv = self.app.post('/api/intervention/sexual_recovery/access_rule',
                content_type='application/json',
                data=json.dumps(d))
        self.assert400(rv)

    def test_and_strats(self):
        # Create a logical 'and' with multiple strategies

        ds_p3p = INTERVENTION.DECISION_SUPPORT_P3P
        ds_p3p.public_access = False
        user = self.test_user
        uw = Organization(name='UW Medicine (University of Washington)')
        INTERVENTION.SEXUAL_RECOVERY.public_access = False
        with SessionScope(db):
            db.session.commit()
        user, uw = map(db.session.merge, (user, uw))

        d = {'name': 'not in SR _and_ in clinc UW',
             'function': 'combine_strategies',
             'kwargs': [
                 {'name': 'strategy_1',
                  'value': 'allow_if_not_in_intervention'},
                 {'name': 'strategy_1_kwargs',
                  'value': [{'name': 'intervention_name',
                             'value': INTERVENTION.SEXUAL_RECOVERY.name}]},
                 {'name': 'strategy_2',
                  'value': 'limit_by_clinic_list'},
                 {'name': 'strategy_2_kwargs',
                  'value': [{'name': 'org_list',
                             'value': [uw.name,]}]}
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

        user.organizations.append(uw)
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
        ucsf = Organization(name='UCSF Medical Center')
        uw = Organization(name='UW Medicine (University of Washington)')
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
                       'value': 'not_in_clinic_list'},
                      {'name': 'strategy_1_kwargs',
                       'value': [{'name': 'org_list',
                                  'value': [ucsf.name,],}]},
                      {'name': 'strategy_2',
                       'value': 'limit_by_clinic_list'},
                      {'name': 'strategy_2_kwargs',
                       'value': [{'name': 'org_list',
                                  'value': [uw.name, ucsf.name]}]},
                  ]},
                 # Not Started TX (strat 3)
                 {'name': 'strategy_3',
                  'value': 'observation_check'},
                 {'name': 'strategy_3_kwargs',
                  'value': [{'name': 'display',
                             'value': CC.TX.codings[0].display},
                            {'name': 'boolean_value', 'value': 'false'}]},
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

        user.save_constrained_observation(
            codeable_concept=CC.TX, value_quantity=CC.FALSE_VALUE,
            audit=Audit(user_id=TEST_USER_ID))
        user.save_constrained_observation(
            codeable_concept=CC.PCaLocalized, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID))
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

    def test_get_empty_user_intervention(self):
        # Get on user w/o user_intervention
        self.login()
        rv = self.app.get('/api/intervention/{i}/user/{u}'.format(
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
                              provider_html='custom ph')
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()

        self.login()
        rv = self.app.get('/api/intervention/{i}/user/{u}'.format(
            i=INTERVENTION.SEXUAL_RECOVERY.name, u=TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(len(rv.json.keys()), 7)
        self.assertEquals(rv.json['user_id'], TEST_USER_ID)
        self.assertEquals(rv.json['access'], 'granted')
        self.assertEquals(rv.json['card_html'], "custom ch")
        self.assertEquals(rv.json['link_label'], "link magic")
        self.assertEquals(rv.json['link_url'], "http://example.com")
        self.assertEquals(rv.json['status_text'], "status example")
        self.assertEquals(rv.json['provider_html'], "custom ph")


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
        rv = self.app.post('/api/intervention/{}/communicate'.format(
                INTERVENTION.DECISION_SUPPORT_P3P.name),
                content_type='application/json',
                data=json.dumps(data))
        self.assert200(rv)
        self.assertEquals(rv.json['message'], 'sent')

        message = EmailMessage.query.one()
        set1 = set((foo.email, boo.email))
        set2 = set(message.recipients.split())
        self.assertEquals(set1, set2)
