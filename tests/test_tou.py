"""Unit test module for terms of use logic"""
import json
from datetime import datetime
from flask_webtest import SessionScope

from tests import TestCase, TEST_USER_ID
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.organization import Organization
from portal.models.research_protocol import ResearchProtocol
from portal.models.tou import ToU
from portal.tasks import deactivate_tous


tou_url = 'http://fake-tou.org'


class TestTou(TestCase):
    """Terms Of Use tests"""

    def test_tou_str(self):
        audit = Audit(
            user_id=TEST_USER_ID, subject_id=TEST_USER_ID,
            comment="Agreed to ToU", context='other')
        tou = ToU(audit=audit, agreement_url=tou_url,
                  type='website terms of use')
        results = "{}".format(tou)
        self.assertTrue(tou_url in results)

    def test_get_tou(self):
        rv = self.client.get('/api/tou')
        self.assert200(rv)
        self.assertTrue('url' in rv.json)

    def test_accept(self):
        self.login()
        data = {'agreement_url': tou_url}
        rv = self.client.post(
            '/api/tou/accepted',
            content_type='application/json',
            data=json.dumps(data))
        self.assert200(rv)
        tou = ToU.query.one()
        self.assertEquals(tou.agreement_url, tou_url)
        self.assertEquals(tou.audit.user_id, TEST_USER_ID)

    def test_accept_w_org(self):
        self.login()
        self.bless_with_basics()
        self.test_user = db.session.merge(self.test_user)
        org_id = self.test_user.organizations.first().id
        data = {'agreement_url': tou_url, 'organization_id': org_id}
        rv = self.client.post(
            '/api/tou/accepted',
            content_type='application/json',
            data=json.dumps(data))
        self.assert200(rv)
        tou = ToU.query.filter(ToU.agreement_url == tou_url).one()
        self.assertEquals(tou.agreement_url, tou_url)
        self.assertEquals(tou.audit.user_id, TEST_USER_ID)
        self.assertEquals(tou.organization_id, org_id)

    def test_service_accept(self):
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)
        data = {'agreement_url': tou_url}
        rv = self.client.post(
            '/api/user/{}/tou/accepted'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        self.assert200(rv)
        tou = ToU.query.one()
        self.assertEquals(tou.agreement_url, tou_url)
        self.assertEquals(tou.audit.user_id, TEST_USER_ID)

    def test_get(self):
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        tou = ToU(audit=audit, agreement_url=tou_url,
                  type='website terms of use')
        with SessionScope(db):
            db.session.add(tou)
            db.session.commit()

        self.login()
        rv = self.client.get('/api/user/{}/tou'.format(TEST_USER_ID))
        doc = json.loads(rv.data)
        self.assert200(rv)
        self.assertEquals(len(doc['tous']), 1)

    def test_get_by_type(self):
        timestamp = datetime.utcnow()
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID,
                      timestamp=timestamp)
        tou = ToU(audit=audit, agreement_url=tou_url,
                  type='privacy policy')
        with SessionScope(db):
            db.session.add(tou)
            db.session.commit()

        self.login()
        rv = self.client.get('/api/user/{}/tou/privacy-policy'.format(
                             TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(rv.json['accepted'],
                          timestamp.strftime("%Y-%m-%dT%H:%M:%S"))
        self.assertEquals(rv.json['type'], 'privacy policy')

    def test_deactivate_tous(self):
        timestamp = datetime.utcnow()

        pptou_audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID,
                            timestamp=timestamp)
        pptou = ToU(audit=pptou_audit, agreement_url=tou_url,
                    type='privacy policy')

        wtou_audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        wtou = ToU(audit=wtou_audit, agreement_url=tou_url,
                   type='website terms of use')

        with SessionScope(db):
            db.session.add(pptou)
            db.session.add(wtou)
            db.session.commit()
        self.test_user, pptou, wtou = map(
            db.session.merge, (self.test_user, pptou, wtou))

        # confirm active
        self.assertTrue(all((pptou.active, wtou.active)))

        # test deactivating single type
        self.test_user.deactivate_tous(self.test_user, ['privacy policy'])
        self.assertFalse(pptou.active)
        self.assertTrue(wtou.active)

        # test deactivating all types
        self.test_user.deactivate_tous(self.test_user)
        self.assertFalse(all((pptou.active, wtou.active)))

    def test_deactivate_tous_by_rp(self):
        timestamp = datetime.utcnow()

        self.add_system_user()
        self.shallow_org_tree()
        parent = Organization.query.get(101)
        child = Organization.query.get(1001)  # child of 101
        lonely_leaf = Organization.query.get(102)
        staff = self.add_user('staff')
        staff_id = staff.id
        self.promote_user(staff, 'staff')
        staff.organizations.append(parent)
        second_user = self.add_user('second@foo.bar')
        second_user_id = second_user.id
        self.promote_user(second_user, 'patient')
        second_user.organizations.append(lonely_leaf)
        self.promote_user(self.test_user, 'patient')
        self.test_user.organizations.append(child)

        rp1 = ResearchProtocol(name='RP 101')
        rp2 = ResearchProtocol(name='RP 102')
        with SessionScope(db):
            db.session.add(rp1)
            db.session.add(rp2)
            db.session.commit()
        rp1, rp2 = map(db.session.merge, (rp1, rp2))
        rp1_name, rp2_name = rp1.name, rp2.name
        parent.research_protocol_id = rp1.id
        lonely_leaf.research_protocol_id = rp2.id

        def gentou(user_id, type):
            return ToU(
                audit=Audit(
                    user_id=user_id, subject_id=user_id, timestamp=timestamp),
                agreement_url=tou_url, type=type)

        pptou = gentou(TEST_USER_ID, 'privacy policy')
        pptou_2 = gentou(second_user_id, 'privacy policy')
        pptou_staff = gentou(staff_id, 'privacy policy')

        wtou = gentou(TEST_USER_ID, 'website terms of use')
        wtou_2 = gentou(second_user_id, 'website terms of use')
        wtou_staff = gentou(staff_id, 'website terms of use')

        tous = (pptou, pptou_2, pptou_staff, wtou, wtou_2, wtou_staff)
        with SessionScope(db):
            for t in tous:
                db.session.add(t)
            db.session.commit()
        self.test_user, second_user, staff, parent = map(
            db.session.merge, (self.test_user, second_user, staff, parent))
        pptou, pptou_2, pptou_staff, wtou, wtou_2, wtou_staff = map(
            db.session.merge, tous)
        self.assertTrue(parent.research_protocol)

        # confirm active
        self.assertTrue(all((
            pptou.active, pptou_2.active, wtou.active, wtou_2.active)))

        # test deactivating single type by rp - should miss second user
        kwargs = {'types': ['privacy policy'], 'research_protocol': rp1_name}
        deactivate_tous(**kwargs)
        self.assertFalse(pptou.active)
        self.assertFalse(pptou_staff.active)
        self.assertTrue(all(
            (pptou_2.active, wtou.active, wtou_2.active, wtou_staff.active)))

        # test limiting to staff on rp both staff and test_user belong to
        # only hits staff
        kwargs['types'] = ['website terms of use']
        kwargs['roles'] = ['staff', 'staff_admin']
        deactivate_tous(**kwargs)
        self.assertFalse(wtou_staff.active)
        self.assertTrue(all((pptou_2.active, wtou.active, wtou_2.active)))



