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
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)

        data = {'user_id': TEST_USER_ID,
                'access': "granted",
                'card_html': "unique HTML set via API",
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
        self.assertEquals(ui.provider_html, data['provider_html'])

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

            for i in range(1,4):
                d = {'function': 'limit_by_clinic',
                     'kwargs': [ {'name': 'organization_name',
                                  'value': 'org{}'.format(i)}, ]
                    }
                strat = AccessStrategy(
                    name="member of org{}".format(i),
                    intervention_id = cp_id,
                    rank=i,
                    function_details=json.dumps(d))
                db.session.add(strat)
            db.session.commit()
        org1, org2, org3 = map(db.session.merge, (org1, org2, org3))
        cp = INTERVENTION.CARE_PLAN
        user = db.session.merge(self.test_user)

        # Prior to associating user with any orgs, shouldn't have access
        self.assertFalse(cp.user_has_access(user))

        # Add association and test again
        user.organizations.append(org3)
        with SessionScope(db):
            db.session.commit()
        user, cp = map(db.session.merge, (user, cp))

        self.assertTrue(cp.user_has_access(user))

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
        self.assertFalse(cp.user_has_access(user))

        # Bless the test user with PCa diagnosis
        user.save_constrained_observation(
            codeable_concept=CC.PCaDIAG, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID))
        with SessionScope(db):
            db.session.commit()
        user, cp = map(db.session.merge, (user, cp))

        self.assertTrue(cp.user_has_access(user))

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
        self.assertFalse(cp.user_has_access(user))

        user.save_constrained_observation(
            codeable_concept=CC.TX, value_quantity=CC.FALSE_VALUE,
            audit=Audit(user_id=TEST_USER_ID))
        with SessionScope(db):
            db.session.commit()
        user, cp = map(db.session.merge, (user, cp))

        # Declaring they started TX, should grant access
        self.assertTrue(cp.user_has_access(user))

        # Say user starts treatment, should lose access
        user.save_constrained_observation(
            codeable_concept=CC.TX, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID))
        with SessionScope(db):
            db.session.commit()
        user, cp = map(db.session.merge, (user, cp))

        self.assertFalse(cp.user_has_access(user))

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
        self.assertTrue(ds_p3p.user_has_access(user))
        self.assertFalse(ds_wc.user_has_access(user))

        # Add user to wisercare, confirm it's the only w/ access

        ui = UserIntervention(user_id=user.id, intervention_id=ds_wc.id,
                              access='granted')
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()
        user, ds_p3p, ds_wc = map(db.session.merge, (user, ds_p3p, ds_wc))

        self.assertFalse(ds_p3p.user_has_access(user))
        self.assertTrue(ds_wc.user_has_access(user))

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
        self.assertEqual(d, data['rules'][0])

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
                  'value': 'limit_by_clinic'},
                 {'name': 'strategy_2_kwargs',
                  'value': [{'name': 'organization_name',
                             'value': uw.name}]}
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
        self.assertFalse(ds_p3p.user_has_access(user))

        user.organizations.append(uw)
        with SessionScope(db):
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))
        # first strat true, second true.  therfore, should be True
        self.assertTrue(ds_p3p.user_has_access(user))

        ui = UserIntervention(
            user_id=user.id,
            intervention_id=INTERVENTION.SEXUAL_RECOVERY.id,
            access='granted')
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))

        # first strat true, second false.  AND should be false
        self.assertFalse(ds_p3p.user_has_access(user))

    def test_p3p_conditions(self):
        # Test the list of conditions expected for p3p
        ds_p3p = INTERVENTION.DECISION_SUPPORT_P3P
        ds_p3p.public_access = False
        user = self.test_user
        uw = Organization(name='UW Medicine (University of Washington)')
        user.organizations.append(uw)
        INTERVENTION.SEXUAL_RECOVERY.public_access = False
        with SessionScope(db):
            db.session.commit()
        user, uw = map(db.session.merge, (user, uw))

        d = {'name': 'not in SR _and_ in clinc UW _and_ not started TX '\
             '_and_ has PCaLocalized',
             'function': 'combine_strategies',
             'kwargs': [
                 # Not in SR
                 {'name': 'strategy_1',
                  'value': 'allow_if_not_in_intervention'},
                 {'name': 'strategy_1_kwargs',
                  'value': [{'name': 'intervention_name',
                             'value': INTERVENTION.SEXUAL_RECOVERY.name}]},
                 # In Clinic UW
                 {'name': 'strategy_2',
                  'value': 'limit_by_clinic'},
                 {'name': 'strategy_2_kwargs',
                  'value': [{'name': 'organization_name',
                             'value': uw.name}]},
                 # Not Started TX
                 {'name': 'strategy_3',
                  'value': 'observation_check'},
                 {'name': 'strategy_3_kwargs',
                  'value': [{'name': 'display',
                             'value': CC.TX.codings[0].display},
                            {'name': 'boolean_value', 'value': 'false'}]},
                 # Has Localized PCa
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
                name=d['name'],
                intervention_id = INTERVENTION.DECISION_SUPPORT_P3P.id,
                function_details=json.dumps(d))
            #print json.dumps(strat.as_json())
            db.session.add(strat)
            db.session.commit()
        user, ds_p3p = map(db.session.merge, (user, ds_p3p))

        # only first two strats true so far, therfore, should be False
        self.assertFalse(ds_p3p.user_has_access(user))

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
        self.assertTrue(ds_p3p.user_has_access(user))

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
                              provider_html='custom ph')
        with SessionScope(db):
            db.session.add(ui)
            db.session.commit()

        self.login()
        rv = self.app.get('/api/intervention/{i}/user/{u}'.format(
            i=INTERVENTION.SEXUAL_RECOVERY.name, u=TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(len(rv.json.keys()), 4)
        self.assertEquals(rv.json['user_id'], TEST_USER_ID)
        self.assertEquals(rv.json['access'], 'granted')
        self.assertEquals(rv.json['card_html'], "custom ch")
        self.assertEquals(rv.json['provider_html'], "custom ph")

    def test_communicate(self):
        email_group = Group(name='test_email')
        foo = self.add_user(username='foo')
        boo = self.add_user(username='boo')
        foo.email = 'foo@example.com'
        boo.email = 'boo@example.com'

        with SessionScope(db):
            map(db.session.add, (foo, boo))
            db.session.commit()
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
