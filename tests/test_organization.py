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
        parent = Organization(id=1, name='fake parent reference')
        with SessionScope(db):
            db.session.add(parent)
            db.session.commit()
        parent = db.session.merge(parent)
        parent_id = parent.id

        with open(os.path.join(
            os.path.dirname(__file__),
            'organization-example-f002-burgers-card.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        # remove the id from the file - doesn't play well with ours
        data.pop('id')
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
        self.login()
        org = Organization(name='test')
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)

        # use api to obtain FHIR
        rv = self.client.get('/api/organization/{}'.format(org.id))
        self.assert200(rv)

    def test_organization_list(self):
        count = Organization.query.count()

        # use api to obtain FHIR bundle
        self.login()
        rv = self.client.get('/api/organization')
        self.assert200(rv)
        bundle = rv.json
        self.assertTrue(bundle['resourceType'], 'Bundle')
        self.assertEquals(len(bundle['entry']), count)

    def test_organization_put(self):
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        with open(os.path.join(
            os.path.dirname(__file__),
            'organization-example-f001-burgers.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        # remove the id from the file - doesn't play well with ours
        data.pop('id')

        # Shove a nearly empty org in the db and then update via the api
        org = Organization(name='test')
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        org_id = org.id

        rv = self.client.put('/api/organization/{}'.format(org_id),
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
        rv = self.client.post('/api/organization',
                           content_type='application/json',
                           data=json.dumps(data))
        self.assert400(rv)

    def test_organization_delete(self):
        (org1_id, org1_name), (org2_id, org2_name) = [
            (org.id, org.name) for org in Organization.query.filter(
                Organization.id > 0).limit(2)]

        # use api to delete one and confirm the other remains
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        rv = self.client.delete('/api/organization/{}'.format(org2_id))
        self.assert200(rv)
        self.assertEquals(Organization.query.get(org2_id), None)
        orgs = Organization.query.all()
        names =  [o.name for o in orgs]
        self.assertTrue('none of the above' in names)
        self.assertTrue(org1_name in names)

    def test_organization_identifiers(self):
        alias = Identifier(
            use='official', system='http://www.zorgkaartnederland.nl/',
            value='my official alias', assigner='Organization/1')
        shortcut = Identifier(
            use='secondary', system=SHORTCUT_ALIAS, value='shortcut')

        org = Organization.query.filter(Organization.id > 0).first()
        before = org.identifiers.count()
        org.identifiers.append(alias)
        org.identifiers.append(shortcut)
        with SessionScope(db):
            db.session.commit()
        org = db.session.merge(org)
        self.assertEquals(org.identifiers.count(), before + 2)

    def test_organization_identifiers_update(self):
        with open(os.path.join(
            os.path.dirname(__file__),
            'organization-example-gastro.json'), 'r') as fhir_data:
            data = json.load(fhir_data)
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()
        before = Organization.query.count()
        rv = self.client.post('/api/organization',
                           content_type='application/json',
                           data=json.dumps(data))
        self.assert200(rv)
        self.assertEquals(Organization.query.count(), before + 1)

        # the gastro file contains a single identifier - add
        # a second one and PUT, expecting we get two total

        alias = Identifier(system=SHORTCUT_ALIAS, value='foobar',
                           use='secondary')
        org = Organization.query.filter_by(name='Gastroenterology').one()
        data['identifier'].append(alias.as_fhir())
        rv = self.client.put('/api/organization/{}'.format(org.id),
                          content_type='application/json',
                          data=json.dumps(data))
        self.assert200(rv)

        # obtain the org from the db, check the identifiers
        org = Organization.query.filter_by(name='Gastroenterology').one()
        self.assertEquals(2, org.identifiers.count())
