"""Unit test module for organization model"""
from flask_webtest import SessionScope
import json
import os

from portal.extensions import db
from portal.system_uri import SHORTCUT_ALIAS
from portal.models.identifier import Identifier
from portal.models.organization import Organization
from portal.models.role import ROLE
from tests import TestCase


class TestOrganization(TestCase):
    """Organization model tests"""

    def test_from_fhir(self):
        with open(os.path.join(
            os.path.dirname(__file__),
            'organization-example-f001-burgers.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        org = Organization.from_fhir(data)
        self.assertEquals(org.addresses[0].line1,
                          data['address'][0]['line'][0])
        self.assertEquals(org.addresses[1].line1,
                          data['address'][1]['line'][0])
        self.assertEquals(org.name, data['name'])
        self.assertEquals(org.phone, "022-655 2300")

    def test_from_fhir_partOf(self):
        # prepopulate database with parent organization
        parent = Organization(name='fake parent reference')
        with SessionScope(db):
            db.session.add(parent)
            db.session.commit()
        parent = db.session.merge(parent)
        parent_id = parent.id

        with open(os.path.join(
            os.path.dirname(__file__),
            'organization-example-f002-burgers-card.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        org = Organization.from_fhir(data)
        self.assertEquals(org.addresses[0].line1,
                          data['address'][0]['line'][0])
        self.assertEquals(org.name, data['name'])
        self.assertEquals(org.phone, "022-655 2320")
        self.assertEquals(org.partOf_id, 1)

        # confirm we can store
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        self.assertTrue(org.id)
        self.assertEquals(org.partOf_id, parent_id)

    def test_as_fhir(self):
        org = Organization(name='Homer\'s Hospital')
        data = org.as_fhir()
        self.assertEquals(org.name, data['name'])

    def test_organization_get(self):
        org = Organization(name='test')
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)

        # use api to obtain FHIR
        self.login()
        rv = self.app.get('/api/organization/{}'.format(org.id))
        self.assert200(rv)

    def test_organization_list(self):
        org1 = Organization(name='test 1')
        org2 = Organization(name='test 2')
        with SessionScope(db):
            db.session.add(org1)
            db.session.add(org2)
            db.session.commit()

        # use api to obtain FHIR bundle
        self.login()
        rv = self.app.get('/api/organization')
        self.assert200(rv)
        bundle = rv.json
        self.assertTrue(bundle['resourceType'], 'Bundle')
        self.assertEquals(len(bundle['entry']), 3)  # 2 + 'none of the above'

    def test_organization_put(self):
        with open(os.path.join(
            os.path.dirname(__file__),
            'organization-example-f001-burgers.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        # Shove a nearly empty org in the db and then update via the api
        org = Organization(name='test')
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        org_id = org.id

        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.app.put('/api/organization/{}'.format(org_id),
                          content_type='application/json',
                          data=json.dumps(data))
        self.assert200(rv)

        # Pull the updated db entry
        org = Organization.query.get(org_id)
        self.assertEquals(org.addresses[0].line1,
                          data['address'][0]['line'][0])
        self.assertEquals(org.addresses[1].line1,
                          data['address'][1]['line'][0])
        self.assertEquals(org.name, data['name'])
        self.assertEquals(org.phone, "022-655 2300")

    def test_organization_post(self):
        with open(os.path.join(
            os.path.dirname(__file__),
            'organization-example-f002-burgers-card.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        # the 002-burgers-card org refers to another - should fail
        # prior to adding the parent (partOf) org
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.app.post('/api/organization',
                           content_type='application/json',
                           data=json.dumps(data))
        self.assert400(rv)

    def test_organization_delete(self):
        org1 = Organization(name='test 1')
        org2 = Organization(name='test 2')
        with SessionScope(db):
            db.session.add(org1)
            db.session.add(org2)
            db.session.commit()
            org2_id = org2.id

        # use api to delete one and confirm the other remains
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.app.delete('/api/organization/{}'.format(org2_id))
        self.assert200(rv)
        # should leave the `none of the above` and test 1
        self.assertEquals(Organization.query.count(), 2)
        orgs = Organization.query.all()
        names =  [o.name for o in orgs]
        self.assertTrue('none of the above' in names)
        self.assertTrue('test 1' in names)

    def test_organization_identifiers(self):
        alias = Identifier(
            use='official', system='http://www.zorgkaartnederland.nl/',
            value='my official alias', assigner='Organization/1')
        shortcut = Identifier(
            use='secondary', system=SHORTCUT_ALIAS, value='ucsf')

        org = Organization(name='test')
        org.identifiers.append(alias)
        org.identifiers.append(shortcut)
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        self.assertEquals(org.identifiers.count(), 2)

    def test_organization_identifiers_update(self):
        with open(os.path.join(
            os.path.dirname(__file__),
            'organization-example-gastro.json'), 'r') as fhir_data:
            data = json.load(fhir_data)
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        org = Organization.query.one()  # only expect the 'none of the above'
        rv = self.app.post('/api/organization',
                           content_type='application/json',
                           data=json.dumps(data))
        self.assert200(rv)
        self.assertEquals(Organization.query.count(), 2)

        # the gastro file contains a single identifier - add
        # a second one and PUT, expecting we get two total

        alias = Identifier(system=SHORTCUT_ALIAS, value='foobar',
                           use='secondary')
        org = Organization.query.filter_by(name='Gastroenterology').one()
        data['identifier'].append(alias.as_fhir())
        rv = self.app.put('/api/organization/{}'.format(org.id),
                          content_type='application/json',
                          data=json.dumps(data))
        self.assert200(rv)

        # obtain the org from the db, check the identifiers
        org = Organization.query.filter_by(name='Gastroenterology').one()
        self.assertEquals(2, org.identifiers.count())
