"""Unit test module for Intervention API"""
from flask.ext.webtest import SessionScope
import json
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.fhir import CC, ValueQuantity
from portal.models.intervention import INTERVENTION
from portal.models.intervention_strategies import AccessStrategy
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
        client = self.add_test_client()
        client.intervention = INTERVENTION.SEXUAL_RECOVERY
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)

        data = {'user_id': TEST_USER_ID,
                'access': "granted",
                'card_html': "unique HTML set via API"}
        rv = self.app.put('/api/intervention/sexual_recovery',
                content_type='application/json',
                data=json.dumps(data))
        self.assert200(rv)

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
        """Test strategy for diagnosis without treatment"""
        # Add access strategies to the care plan intervention
        cp = INTERVENTION.CARE_PLAN
        cp.public_access = False  # turn off public access to force strategy
        cp_id = cp.id

        with SessionScope(db):
            d = {'function': 'diagnosis_w_o_tx', 'kwargs': []}
            strat = AccessStrategy(
                name="test strategy",
                intervention_id = cp_id,
                function_details=json.dumps(d))
            db.session.add(strat)
            db.session.commit()
        cp = INTERVENTION.CARE_PLAN
        user = db.session.merge(self.test_user)

        # Prior to associating user with any orgs, shouldn't have access
        self.assertFalse(cp.user_has_access(user))

        # Bless the test user with PCa diagnosis (but no TX)
        truthiness = ValueQuantity(value='true', units='boolean')
        user.save_constrained_observation(
            codeable_concept=CC.PCaDIAG, value_quantity=truthiness,
            audit=Audit(user_id=TEST_USER_ID))
        with SessionScope(db):
            db.session.commit()
        user, cp = map(db.session.merge, (user, cp))

        self.assertTrue(cp.user_has_access(user))

    def test_strat_from_json(self):
        """Create access strategy from json"""
        d = {'name': 'unit test example',
             'function_details': {
                 'function': 'diagnosis_w_o_tx',
                 'kwargs': []
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
                 'function': 'diagnosis_w_o_tx',
                 'kwargs': []
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
