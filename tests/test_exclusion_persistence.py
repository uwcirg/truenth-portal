import json
from os.path import join as path_join
from shutil import rmtree
from tempfile import mkdtemp

from flask_webtest import SessionScope

from portal.config.exclusion_persistence import (
    client_users_filter,
    ExclusionPersistence,
    staging_exclusions,
)
from portal.database import db
from portal.models.auth import AuthProvider, Token, create_service_token
from portal.models.client import Client
from portal.models.intervention import INTERVENTION, Intervention
from portal.models.user import User, UserRelationship
from tests import TEST_USER_ID, TestCase


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

        self.assertEqual(tc1.callback_url, 'http://callback.one')
        self.assertEqual(tc2._redirect_uris, 'http://test_two.org')

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

        self.assertEqual(result.link_url, 'http://retain.this')
        self.assertEqual(result.description, 'prod description')

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
        self.assertEqual(expected, len(serial_form['entry']))

        # Modify/delete some internal db values and confirm reapplication of
        # persistence restores desired values
        owner = db.session.merge(owner)
        owner.email = str(owner_id)

        # just expecting the one service token.  purge it and the
        # owner (the service user) and the owner's auth_provider
        self.assertEqual(Token.query.count(), 1)
        service_user_id = Token.query.one().user_id
        b4 = User.query.count()
        self.assertEqual(UserRelationship.query.count(), 1)
        self.assertEqual(AuthProvider.query.count(), 1)
        with SessionScope(db):
            AuthProvider.query.delete()
            Token.query.delete()
            UserRelationship.query.delete()
            User.query.filter_by(id=service_user_id).delete()
            db.session.commit()
        self.assertEqual(AuthProvider.query.count(), 0)
        self.assertEqual(Token.query.count(), 0)
        self.assertEqual(UserRelationship.query.count(), 0)
        self.assertEqual(b4 - 1, User.query.count())

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
        self.assertEqual(result.email, 'sm-owner@gmail.com')
        self.assertEqual(AuthProvider.query.count(), 1)
        self.assertEqual(Token.query.count(), 1)
        self.assertEqual(UserRelationship.query.count(), 1)


    def test_preflight_valid(self):
        # setup pre-flight conditions expected to pass
        ds_p3p = INTERVENTION.decision_support_p3p
        ds_client = Client(
            client_id='12345', client_secret='54321', user_id=TEST_USER_ID,
            intervention=ds_p3p, _redirect_uris='http://testsite.org',
            callback_url='http://callback.one')
        service = self.add_service_user(sponsor=self.test_user)

        with SessionScope(db):
            db.session.add(ds_client)
            db.session.commit()

        ds_client = db.session.merge(ds_client)
        service = db.session.merge(service)
        create_service_token(client=ds_client, user=service)

        # Export
        for model in staging_exclusions:
            ex = ExclusionPersistence(
                model_class=model.cls, lookup_field=model.lookup_field,
                limit_to_attributes=model.limit_to_attributes,
                filter_query=model.filter_query,
                target_dir=self.tmpdir)
            ex.export()

        self.assertEqual(Token.query.count(), 1)

        # Delete service account, expect it to return
        with SessionScope(db):
            db.session.delete(service)
            db.session.commit()

        self.assertEqual(Token.query.count(), 0)
