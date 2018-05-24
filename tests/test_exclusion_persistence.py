from flask_webtest import SessionScope
import json
from os.path import join as path_join
from shutil import rmtree
from tests import TestCase, TEST_USER_ID
from tempfile import mkdtemp

from portal.models.auth import AuthProvider, create_service_token, Token
from portal.config.site_persistence import (
    staging_exclusions, client_users_filter)
from portal.config.exclusion_persistence import ExclusionPersistence
from portal.database import db
from portal.models.client import Client
from portal.models.intervention import Intervention, INTERVENTION
from portal.models.user import User, UserRelationship


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
                limit_to_attributes=model.limit_to_attributes,
                filter_query=model.filter_query,
                target_dir=self.tmpdir)
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
                limit_to_attributes=model.limit_to_attributes,
                filter_query=model.filter_query,
                target_dir=self.tmpdir)
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
                limit_to_attributes=model.limit_to_attributes,
                filter_query=model.filter_query,
                target_dir=self.tmpdir)
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
                limit_to_attributes=model.limit_to_attributes,
                filter_query=model.filter_query,
                target_dir=self.tmpdir)
            ex.import_(keep_unmentioned=True)

        result = Intervention.query.filter(Intervention.name == 'alvin').one()

        self.assertEquals(result.link_url, 'http://retain.this')
        self.assertEquals(result.description, 'prod description')

    def test_connected_user(self):
        """User and service tokens connected with intervention should survive"""
        owner = self.add_user('sm-owner@gmail.com')
        self.promote_user(user=owner, role_name='application_developer')
        owner = db.session.merge(owner)
        owner_id = owner.id
        service = self.add_service_user(sponsor=owner)

        # give the owner a fake auth_provider row
        ap = AuthProvider(user_id=owner_id, provider_id=1)
        with SessionScope(db):
            db.session.add(ap)
            db.session.commit()

        sm_client = Client(
            client_id='abc_123', client_secret='shh', user_id=owner_id,
            _redirect_uris='http://testsite.org',
            callback_url='http://callback.one')
        with SessionScope(db):
            db.session.add(sm_client)

        # give the owner a fake auth_provider row
        ap = AuthProvider(user=owner, provider_id=1)

        service, sm_client = map(db.session.merge, (service, sm_client))
        create_service_token(client=sm_client, user=service)
        sm = INTERVENTION.SELF_MANAGEMENT
        sm.client = sm_client

        # Setup complete - SM has an owner, a service user and a service token
        # generate the full export
        for model in staging_exclusions:
            ep = ExclusionPersistence(
                model_class=model.cls, lookup_field=model.lookup_field,
                limit_to_attributes=model.limit_to_attributes,
                filter_query=model.filter_query,
                target_dir=self.tmpdir)
            ep.export()

        # Confirm filter worked
        expected = client_users_filter().count()
        with open(path_join(self.tmpdir, 'User.json')) as f:
            serial_form = json.loads(f.read())
        self.assertEquals(expected, len(serial_form['entry']))

        # Modify/delete some internal db values and confirm reapplication of
        # persistence restores desired values
        owner = db.session.merge(owner)
        owner.email = str(owner_id)

        # just expecting the one service token.  purge it and the
        # owner (the service user) and the owner's auth_provider
        self.assertEquals(Token.query.count(), 1)
        service_user_id = Token.query.one().user_id
        b4 = User.query.count()
        self.assertEquals(UserRelationship.query.count(), 1)
        self.assertEquals(AuthProvider.query.count(), 1)
        with SessionScope(db):
            AuthProvider.query.delete()
            Token.query.delete()
            UserRelationship.query.delete()
            User.query.filter_by(id=service_user_id).delete()
            db.session.commit()
        self.assertEquals(AuthProvider.query.count(), 0)
        self.assertEquals(Token.query.count(), 0)
        self.assertEquals(UserRelationship.query.count(), 0)
        self.assertEquals(b4 - 1, User.query.count())

        for model in staging_exclusions:
            ep = ExclusionPersistence(
                model_class=model.cls, lookup_field=model.lookup_field,
                limit_to_attributes=model.limit_to_attributes,
                filter_query=model.filter_query,
                target_dir=self.tmpdir)
            if model.cls.__name__ == 'User':
                pass
            ep.import_(keep_unmentioned=True)

        result = User.query.get(owner_id)
        self.assertEquals(result.email, 'sm-owner@gmail.com')
        self.assertEquals(AuthProvider.query.count(), 1)
        self.assertEquals(Token.query.count(), 1)
        self.assertEquals(UserRelationship.query.count(), 1)
