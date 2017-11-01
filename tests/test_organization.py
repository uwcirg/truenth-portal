"""Unit test module for organization model"""
from flask_webtest import SessionScope
import json
import os

from portal.extensions import db
from portal.system_uri import PRACTICE_REGION, SHORTCUT_ALIAS
from portal.models.fhir import Coding
from portal.models.identifier import Identifier
from portal.models.organization import Organization, OrgTree
from portal.models.organization import OrganizationIdentifier
from portal.models.role import ROLE
from tests import TestCase


class TestOrganization(TestCase):
    """Organization model tests"""

    def test_from_fhir(self):
        with open(os.path.join(
            os.path.dirname(__file__),
            'organization-example-f001-burgers.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        #prepopuate database with matching locale
        Coding.from_fhir({'code': 'en_AU', 'display': 'Australian English',
                  'system': "urn:ietf:bcp:47"})
        org = Organization.from_fhir(data)
        self.assertEquals(org.addresses[0].line1,
                          data['address'][0]['line'][0])
        self.assertEquals(org.addresses[1].line1,
                          data['address'][1]['line'][0])
        self.assertEquals(org.name, data['name'])
        self.assertEquals(org.phone, "022-655 2300")
        self.assertTrue(org.use_specific_codings)
        self.assertTrue(org.race_codings)
        self.assertFalse(org.ethnicity_codings)
        self.assertEquals(org.locales.count(),1)
        self.assertEquals(org.default_locale, "en_AU")
        self.assertEquals(org._timezone, "US/Pacific")

    def test_from_fhir_partOf(self):
        # prepopulate database with parent organization
        parent = Organization(id=101, name='fake parent reference')
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
        self.assertEquals(org.partOf_id, parent_id)

        # confirm we can store
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        self.assertTrue(org.id)
        self.assertEquals(org.partOf_id, parent_id)

    def test_timezone_inheritance(self):
        parent = Organization(id=101, name='parentOrg')
        org = Organization(id=102, name='org', partOf_id=101)

        # test that with no timezones set, defaults to UTC
        with SessionScope(db):
            db.session.add(parent)
            db.session.add(org)
            db.session.commit()
        parent, org = map(db.session.merge,(parent, org))
        self.assertEquals(org.timezone, 'UTC')

        # test that timezone-less child org inherits from parent
        parent.timezone = 'Asia/Tokyo'
        with SessionScope(db):
            db.session.add(parent)
            db.session.commit()
        parent, org = map(db.session.merge,(parent, org))
        self.assertEquals(org.timezone, 'Asia/Tokyo')

        # test that child org with timezone does NOT inherit from parent
        org.timezone = 'Europe/Rome'
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        self.assertEquals(org.timezone, 'Europe/Rome')

    def test_as_fhir(self):
        org = Organization(name='Homer\'s Hospital')
        org.use_specific_codings = True
        org.race_codings = False
        data = org.as_fhir()
        self.assertEquals(org.name, data['name'])
        self.assertTrue(data['use_specific_codings'])
        self.assertFalse(data['race_codings'])

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

    def test_organization_get_by_identifier(self):
        org_id_system = "testsystem"
        org_id_value = "testval"
        self.login()
        org = Organization(name='test',id=999)
        ident = Identifier(id=99,system=org_id_system,value=org_id_value)
        org_ident = OrganizationIdentifier(organization_id=999,
                                            identifier_id=99)
        with SessionScope(db):
            db.session.add(org)
            db.session.add(ident)
            db.session.commit()
            db.session.add(org_ident)
            db.session.commit()

        # use api to obtain FHIR
        rv = self.client.get('/api/organization/{}/{}'.format(org_id_system,
                                            org_id_value))
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

    def test_organization_search(self):
        self.shallow_org_tree()
        count = Organization.query.count()
        self.assertTrue(count > 1)

        # add region to one org, we should get only that one back
        region = Identifier(value='state:NY', system=PRACTICE_REGION)
        with SessionScope(db):
            db.session.add(region)
            db.session.commit()
        region = db.session.merge(region)
        oi = OrganizationIdentifier(organization_id=1001,
                                    identifier_id=region.id)
        with SessionScope(db):
            db.session.add(oi)
            db.session.commit()

        # use api to obtain FHIR bundle
        self.login()
        rv = self.client.get('/api/organization?state=NY')
        self.assert200(rv)
        bundle = rv.json
        self.assertTrue(bundle['resourceType'], 'Bundle')
        self.assertEquals(len(bundle['entry']), 1)

    def test_organization_inheritence_search(self):
        # Region at top should apply to leaves
        self.deepen_org_tree()
        count = Organization.query.count()
        self.assertTrue(count > 3)

        # add region to one mid-level parent org with two children,
        # we should get only those three
        region = Identifier(value='state:NY', system=PRACTICE_REGION)
        with SessionScope(db):
            db.session.add(region)
            db.session.commit()
        region = db.session.merge(region)
        oi = OrganizationIdentifier(organization_id=1002,
                                    identifier_id=region.id)
        with SessionScope(db):
            db.session.add(oi)
            db.session.commit()

        # use api to obtain FHIR bundle
        self.login()
        rv = self.client.get('/api/organization?state=NY')
        self.assert200(rv)
        bundle = rv.json
        self.assertTrue(bundle['resourceType'], 'Bundle')
        self.assertEquals(len(bundle['entry']), 3)

        # add filter to restrict to just the leaves
        rv = self.client.get('/api/organization?state=NY&filter=leaves')
        self.assert200(rv)
        bundle = rv.json
        self.assertTrue(bundle['resourceType'], 'Bundle')
        self.assertEquals(len(bundle['entry']), 2)

    def test_organization_filter(self):
        # Filter w/o a search term
        self.deepen_org_tree()
        count = Organization.query.count()
        self.assertTrue(count > 6)

        # Filter w/o search should give a short list of orgs
        rv = self.client.get('/api/organization?filter=leaves')
        self.assert200(rv)
        bundle = rv.json
        self.assertTrue(bundle['resourceType'], 'Bundle')
        self.assertEquals(len(bundle['entry']), 3)

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

        #prepopuate database with matching locale
        Coding.from_fhir({'code': 'en_AU', 'display': 'Australian English',
                  'system': "urn:ietf:bcp:47"})

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
        self.shallow_org_tree()
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

        self.shallow_org_tree()
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

    def test_org_tree_nodes(self):
        self.shallow_org_tree()
        with self.assertRaises(ValueError) as context:
            OrgTree().all_leaves_below_id(0)  # none of the above
        self.assertTrue('not found' in context.exception.message)

        nodes = OrgTree().all_leaves_below_id(101)
        self.assertEquals(1, len(nodes))

    def test_deeper_org_tree(self):
        self.deepen_org_tree()
        leaves = OrgTree().all_leaves_below_id(102)
        self.assertTrue(len(leaves) == 2)
        self.assertTrue(10032 in leaves)
        self.assertTrue(10031 in leaves)

    def test_staff_leaves(self):
        # test staff with several org associations produces correct list
        self.deepen_org_tree()
        # Make staff with org associations at two levels
        self.promote_user(role_name=ROLE.STAFF)

        orgs = Organization.query.filter(Organization.id.in_((101, 102)))
        for o in orgs:
            self.test_user.organizations.append(o)
        with SessionScope(db):
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)

        # Should now find children of 101 (1001) and leaf children
        # of 102 (10031, 10032) for total of 3 leaf nodes
        leaves = self.test_user.leaf_organizations()
        self.assertEquals(len(leaves), 3)
        self.assertTrue(1001 in leaves)
        self.assertTrue(10031 in leaves)
        self.assertTrue(10032 in leaves)

    def test_all_leaves(self):
        # can we get a list of just the leaf orgs
        self.deepen_org_tree()
        leaves = OrgTree().all_leaf_ids()
        self.assertEquals(len(leaves), 3)
        for i in (1001, 10031, 10032):
            self.assertTrue(i in leaves)

    def test_here_and_below_id(self):
        self.deepen_org_tree()
        nodes = OrgTree().here_and_below_id(102)
        self.assertEquals(len(nodes), 4)
        for i in (102, 1002, 10031, 10032):
            self.assertTrue(i in nodes)

    def test_visible_patients_on_none(self):
        # Add none of the above to users orgs
        self.test_user.organizations.append(Organization.query.get(0))
        self.promote_user(role_name=ROLE.STAFF)
        self.test_user = db.session.merge(self.test_user)

        patients_list = OrgTree().visible_patients(self.test_user)
        self.assertEquals(len(patients_list), 0)
