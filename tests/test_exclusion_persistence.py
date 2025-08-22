import json
from os.path import join as path_join
from shutil import rmtree
from tempfile import mkdtemp

from flask_webtest import SessionScope

from portal.config.exclusion_persistence import (
    ExclusionPersistence,
    client_users_filter,
    staging_exclusions,
)
from portal.config.site_persistence import SitePersistence
from portal.database import db
from portal.models.auth import AuthProvider, Token, create_service_token
from portal.models.client import Client
from portal.models.intervention import INTERVENTION, Intervention
from portal.models.role import ROLE, Role
from portal.models.user import User, UserRelationship, UserRoles
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

        assert tc1.callback_url == 'http://callback.one'
        assert tc2._redirect_uris == 'http://test_two.org'

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

        assert result.link_url == 'http://retain.this'
        assert result.description == 'prod description'

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
        assert expected == len(serial_form['entry'])

        # Modify/delete some internal db values and confirm reapplication of
        # persistence restores desired values
        owner = db.session.merge(owner)
        owner.email = f"{owner_id}@example.com"

        # just expecting the one service token.  purge it and the
        # owner (the service user) and the owner's auth_provider
        assert Token.query.count() == 1
        service_user_id = Token.query.one().user_id
        b4 = User.query.count()
        assert UserRelationship.query.count() == 1
        assert AuthProvider.query.count() == 1
        with SessionScope(db):
            AuthProvider.query.delete()
            Token.query.delete()
            UserRelationship.query.delete()
            User.query.filter_by(id=service_user_id).delete()
            db.session.commit()
        assert AuthProvider.query.count() == 0
        assert Token.query.count() == 0
        assert UserRelationship.query.count() == 0
        assert User.query.count() == b4 - 1

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
        assert result.email == 'sm-owner@gmail.com'
        assert AuthProvider.query.count() == 1
        assert Token.query.count() == 1
        assert UserRelationship.query.count() == 1

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
        sp = SitePersistence(target_dir=self.tmpdir)
        sp.export(staging_exclusion=True)

        assert Token.query.count() == 1

        # Delete service account, expect it to return
        with SessionScope(db):
            db.session.delete(service)
            db.session.commit()

        assert User.query.count() == 1
        assert Token.query.count() == 0

        # Import
        sp.import_(keep_unmentioned=True, staging_exclusion=True)

        assert Token.query.count() == 1
        assert User.query.count() == 2

    def test_preflight_invalid_service_user(self):
        # setup pre-flight conditions expected to fail
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
        service_id = service.id
        create_service_token(client=ds_client, user=service)

        # Export
        sp = SitePersistence(target_dir=self.tmpdir)
        sp.export(staging_exclusion=True)

        assert Token.query.count() == 1

        # Delete service account, and put fake patient in its place
        with SessionScope(db):
            db.session.delete(service)
            db.session.commit()

        assert User.query.count() == 1
        assert Token.query.count() == 0

        patient_role_id = Role.query.filter_by(
            name=ROLE.PATIENT.value).one().id
        patient_in_way = User(
            id=service_id, first_name='in the', last_name='way',
            email='intheway@here.com')
        with SessionScope(db):
            db.session.add(patient_in_way)
            db.session.commit()
        with SessionScope(db):
            db.session.add(UserRoles(
                user_id=service_id, role_id=patient_role_id))
            db.session.commit()

        # Import should now fail
        with self.assertRaises(ValueError) as context:
            sp.import_(keep_unmentioned=True, staging_exclusion=True)

        assert 'intheway@here.com' in str(context.exception)
