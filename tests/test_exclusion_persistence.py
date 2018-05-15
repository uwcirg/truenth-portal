from flask_webtest import SessionScope
from shutil import rmtree
from tests import TestCase, TEST_USER_ID
from tempfile import mkdtemp

from portal.config.site_persistence import staging_exclusions
from portal.config.model_persistence import ExclusionPersistence
from portal.database import db
from portal.models.client import Client
from portal.models.intervention import Intervention


class TestExclusionPersistence(TestCase):

    def setUp(self):
        super(TestExclusionPersistence, self).setUp()
        self.tmpdir = mkdtemp()

    def tearDown(self):
        super(TestExclusionPersistence, self).tearDown()
        rmtree(self.tmpdir)

    def testClient(self):
        tc1 = Client(
            client_id='123_abc', client_secret='shh', user_id=TEST_USER_ID,
            _redirect_uris='http://testsite.org',
            callback_url='http://callback.one')
        tc2 = Client(
            client_id='234_bcd', client_secret='shh-two', user_id=TEST_USER_ID,
            _redirect_uris='http://test_two.org',
            callback_url='http://callback.two')
        with SessionScope(db):
            db.session.add(tc1)
            db.session.add(tc2)
            db.session.commit()

        client_ex = [ex for ex in staging_exclusions if ex.cls == Client]
        for model in client_ex:
            ex = ExclusionPersistence(
                model_class=model.cls, lookup_field=model.lookup_field,
                attributes=model.attributes, target_dir=self.tmpdir)
            ex.export()

        # Modify the client in the db - then restore to confirm change
        tc1, tc2 = map(db.session.merge, (tc1, tc2))
        tc1.callback_url = 'http://prod1/callback'
        tc2._redirect_uris = 'https://prod.server'
        with SessionScope(db):
            db.session.commit()

        for model in client_ex:
            ex = ExclusionPersistence(
                model_class=model.cls, lookup_field=model.lookup_field,
                attributes=model.attributes, target_dir=self.tmpdir)
            ex.import_(keep_unmentioned=True)

        tc1 = Client.query.filter(Client.client_id == '123_abc').one()
        tc2 = Client.query.filter(Client.client_id == '234_bcd').one()

        self.assertEquals(tc1.callback_url, 'http://callback.one')
        self.assertEquals(tc2._redirect_uris, 'http://test_two.org')

    def testIntervention(self):
        t1 = Intervention(
            name='alvin', description='stage description',
            link_url='http://retain.this')
        with SessionScope(db):
            db.session.add(t1)
            db.session.commit()

        inter_ex = [ex for ex in staging_exclusions if ex.cls == Intervention]
        for model in inter_ex:
            ex = ExclusionPersistence(
                model_class=model.cls, lookup_field=model.lookup_field,
                attributes=model.attributes, target_dir=self.tmpdir)
            ex.export()

        # Modify the intervention as if prod - then restore to confirm change
        t1 = db.session.merge(t1)
        t1.description = 'prod description'
        t1.link_url = 'http://prod_link'
        with SessionScope(db):
            db.session.commit()

        for model in inter_ex:
            ex = ExclusionPersistence(
                model_class=model.cls, lookup_field=model.lookup_field,
                attributes=model.attributes, target_dir=self.tmpdir)
            ex.import_(keep_unmentioned=True)

        result = Intervention.query.filter(Intervention.name == 'alvin').one()

        self.assertEquals(result.link_url, 'http://retain.this')
        self.assertEquals(result.description, 'prod description')
