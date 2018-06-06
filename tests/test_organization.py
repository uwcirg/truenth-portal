"""Unit test module for organization model"""
from datetime import datetime, timedelta
from flask_webtest import SessionScope
import json
import os
from urllib import quote_plus

from portal.extensions import db
from portal.system_uri import (
    IETF_LANGUAGE_TAG,
    PRACTICE_REGION,
    SHORTCUT_ALIAS,
    SHORTNAME_ID,
    US_NPI)
from portal.models.coding import Coding
from portal.models.identifier import Identifier
from portal.models.locale import LocaleConstants
from portal.models.organization import (
    LocaleExtension,
    Organization,
    OrganizationIdentifier,
    OrganizationResearchProtocol,
    OrgTree,
    ResearchProtocolExtension)
from portal.models.reference import Reference
from portal.models.research_protocol import ResearchProtocol
from portal.models.role import ROLE
from tests import TestCase, TEST_USER_ID


class TestOrganization(TestCase):
    """Organization model tests"""

    def test_from_fhir(self):
        with open(os.path.join(
            os.path.dirname(__file__),
            'organization-example-f001-burgers.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        #prepopuate database with matching locale
        Coding.from_fhir({'code': 'en_AU', 'display': 'Australian English',
                  'system': IETF_LANGUAGE_TAG})
        org = Organization.from_fhir(data)
        self.assertEqual(org.addresses[0].line1,
                          data['address'][0]['line'][0])
        self.assertEqual(org.addresses[1].line1,
                          data['address'][1]['line'][0])
        self.assertEqual(org.name, data['name'])
        self.assertEqual(org.phone, "022-655 2300")
        self.assertTrue(org.use_specific_codings)
        self.assertTrue(org.race_codings)
        self.assertFalse(org.ethnicity_codings)
        self.assertEqual(org.locales.count(), 1)
        self.assertEqual(org.default_locale, "en_AU")
        self.assertEqual(org._timezone, "US/Pacific")

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

        self.assertEqual(org.addresses[0].line1,
                          data['address'][0]['line'][0])
        self.assertEqual(org.name, data['name'])
        self.assertEqual(org.phone, "022-655 2320")
        self.assertEqual(org.partOf_id, parent_id)

        # confirm we can store
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        self.assertTrue(org.id)
        self.assertEqual(org.partOf_id, parent_id)

    def test_timezone_inheritance(self):
        parent = Organization(id=101, name='parentOrg')
        org = Organization(id=102, name='org', partOf_id=101)

        # test that with no timezones set, defaults to UTC
        with SessionScope(db):
            db.session.add(parent)
            db.session.add(org)
            db.session.commit()
        parent, org = map(db.session.merge,(parent, org))
        self.assertEqual(org.timezone, 'UTC')

        # test that timezone-less child org inherits from parent
        parent.timezone = 'Asia/Tokyo'
        with SessionScope(db):
            db.session.add(parent)
            db.session.commit()
        parent, org = map(db.session.merge,(parent, org))
        self.assertEqual(org.timezone, 'Asia/Tokyo')

        # test that child org with timezone does NOT inherit from parent
        org.timezone = 'Europe/Rome'
        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        self.assertEqual(org.timezone, 'Europe/Rome')

    def test_as_fhir(self):
        org = Organization(name='Homer\'s Hospital')
        org.use_specific_codings = True
        org.race_codings = False
        data = org.as_fhir()
        self.assertEqual(org.name, data['name'])
        self.assertTrue(data['use_specific_codings'])
        self.assertFalse(data['race_codings'])

    def test_multiple_rps_in_fhir(self):
        yesterday = datetime.utcnow() - timedelta(days=1)
        lastyear = datetime.utcnow() - timedelta(days=365)
        org = Organization(name='Testy')
        rp1 = ResearchProtocol(name='rp1')
        rp2 = ResearchProtocol(name='yesterday')
        rp3 = ResearchProtocol(name='last year')
        with SessionScope(db):
            map(db.session.add, (org, rp1, rp2, rp3))
            db.session.commit()
        org, rp1, rp2, rp3 = map(db.session.merge, (org, rp1, rp2, rp3))
        o_rp1 = OrganizationResearchProtocol(
            research_protocol=rp1, organization=org)
        o_rp2 = OrganizationResearchProtocol(
            research_protocol=rp2, organization=org, retired_as_of=yesterday)
        o_rp3 = OrganizationResearchProtocol(
            research_protocol=rp3, organization=org, retired_as_of=lastyear)
        with SessionScope(db):
            map(db.session.add, (o_rp1, o_rp2, o_rp3))
            db.session.commit()
        org, rp1, rp2, rp3 = map(db.session.merge, (org, rp1, rp2, rp3))
        data = org.as_fhir()
        self.assertEqual(org.name, data['name'])
        rps = [
            extension for extension in data['extension']
            if extension['url'] == ResearchProtocolExtension.extension_url]

        self.assertEqual(len(rps), 1)
        self.assertEqual(len(rps[0]['research_protocols']), 3)

        # confirm the order is descending in the custom accessor method
        results = [(rp, retired) for rp, retired in org.rps_w_retired()]
        self.assertEqual(
            [(rp1, None), (rp2, yesterday), (rp3, lastyear)],
            results)

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
        org_id_system = "http://test/system"
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
        rv = self.client.get(
            '/api/organization?system={system}&value={value}'.format(
                system=quote_plus(org_id_system), value=org_id_value))
        self.assert200(rv)
        self.assertEqual(rv.json['total'], 1)
        self.assertEqual(rv.json['entry'][0]['id'], 999)

        # use alternative API to obtain organization
        rv = self.client.get(
            '/api/organization/{value}?system={system}'.format(
                system=quote_plus(org_id_system), value=org_id_value))
        self.assert200(rv)
        fetched = Organization.from_fhir(rv.json)
        org = db.session.merge(org)
        self.assertEqual(org.id, fetched.id)
        self.assertEqual(org.name, fetched.name)

    def test_org_missing_identifier(self):
        # should get 404 w/o finding a match
        rv = self.client.get(
            '/api/organization/{value}?system={system}'.format(
                system=quote_plus('http://nonsense.org'), value='123-45'))
        self.assert404(rv)

    def test_organization_list(self):
        count = Organization.query.count()

        # use api to obtain FHIR bundle
        self.login()
        rv = self.client.get('/api/organization')
        self.assert200(rv)
        bundle = rv.json
        self.assertTrue(bundle['resourceType'], 'Bundle')
        self.assertEqual(len(bundle['entry']), count)

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
        self.assertEqual(len(bundle['entry']), 1)

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
        self.assertEqual(len(bundle['entry']), 3)

        # add filter to restrict to just the leaves
        rv = self.client.get('/api/organization?state=NY&filter=leaves')
        self.assert200(rv)
        bundle = rv.json
        self.assertTrue(bundle['resourceType'], 'Bundle')
        self.assertEqual(len(bundle['entry']), 2)

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
        self.assertEqual(len(bundle['entry']), 3)

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
        self.assertEqual(org.addresses[0].line1,
                          data['address'][0]['line'][0])
        self.assertEqual(org.addresses[1].line1,
                          data['address'][1]['line'][0])
        self.assertEqual(org.name, data['name'])
        self.assertEqual(org.phone, "022-655 2300")

    def test_organization_put_update(self):
        # confirm unmentioned fields persist
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        en_AU = LocaleConstants().AustralianEnglish

        # Populate db with complet org, and set many fields
        org = Organization(
            name='test', phone='800-800-5665', timezone='US/Pacific')
        org.identifiers.append(Identifier(
            value='state:NY', system=PRACTICE_REGION))
        org.locales.append(en_AU)
        org.default_locale = 'en_AU'

        with SessionScope(db):
            db.session.add(org)
            db.session.commit()
        org = db.session.merge(org)
        org_id = org.id
        data = org.as_fhir()

        # Now strip down the representation - confirm a post doesn't
        # wipe unmentioned fields
        del data['extension']
        del data['telecom']
        del data['language']

        rv = self.client.put(
            '/api/organization/{}'.format(org_id),
            content_type='application/json',
            data=json.dumps(data))
        self.assert200(rv)

        # Pull the updated db entry
        org = Organization.query.get(org_id)
        en_AU = db.session.merge(en_AU)

        # Confirm all the unmentioned entries survived
        self.assertEqual(org.phone, '800-800-5665')
        self.assertEqual(org.default_locale, 'en_AU')
        self.assertEqual(org.locales[0], en_AU)
        self.assertEqual(org.timezone, 'US/Pacific')

    def test_organization_extension_update(self):
        # confirm clearing one of several extensions works
        self.promote_user(role_name=ROLE.ADMIN)
        self.login()

        en_AU = LocaleConstants().AustralianEnglish

        # Populate db with complete org, and set many fields
        org = Organization(
            name='test', phone='800-800-5665', timezone='US/Pacific')
        org.identifiers.append(Identifier(
            value='state:NY', system=PRACTICE_REGION))
        org.locales.append(en_AU)
        org.default_locale = 'en_AU'
        rp = ResearchProtocol(name='rp1')

        with SessionScope(db):
            db.session.add(rp)
            db.session.add(org)
            db.session.commit()
        org, rp = map(db.session.merge, (org, rp))
        org_id, rp_id = org.id, rp.id
        org.research_protocols.append(rp)
        data = org.as_fhir()
        input = {k: v for k, v in data.items() if k in (
            'name', 'resourceType')}

        # Replace locale extension with null value, copy
        # over others.
        input['extension'] = [
            e for e in data['extension']
            if e['url'] != LocaleExtension.extension_url]
        input['extension'].append({'url': LocaleExtension.extension_url})

        rv = self.client.put(
            '/api/organization/{}'.format(org_id),
            content_type='application/json',
            data=json.dumps(input))
        self.assert200(rv)

        # Pull the updated db entry
        org = Organization.query.get(org_id)
        en_AU = db.session.merge(en_AU)

        # Confirm all the unmentioned entries survived
        self.assertEqual(org.phone, '800-800-5665')
        self.assertEqual(org.default_locale, 'en_AU')
        self.assertEqual(org.locales.count(), 0)
        self.assertEqual(org.timezone, 'US/Pacific')
        self.assertEqual(
            org.research_protocol(as_of_date=datetime.utcnow()).id, rp_id)

        # Confirm empty extension isn't included in result
        results = json.loads(rv.data)
        for e in results['extension']:
            assert 'url' in e
            assert len(e.keys()) > 1

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
        self.assertEqual(Organization.query.get(org2_id), None)
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
        self.assertEqual(org.identifiers.count(), before + 2)

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
        self.assertEqual(Organization.query.count(), before + 1)

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
        self.assertEqual(2, org.identifiers.count())

    def test_shortname(self):
        shorty = Identifier(system=SHORTNAME_ID, value='shorty')
        self.shallow_org_tree()
        org = Organization.query.filter(Organization.id > 0).first()
        # prior to adding shortname, should just get org name
        self.assertEqual(org.name, org.shortname)

        org.identifiers.append(shorty)
        with SessionScope(db):
            db.session.commit()
        org = db.session.merge(org)
        # after, should get the shortname
        self.assertEqual(org.shortname, 'shorty')

    def test_org_tree_nodes(self):
        self.shallow_org_tree()
        with self.assertRaises(ValueError) as context:
            OrgTree().all_leaves_below_id(0)  # none of the above
        self.assertTrue('not found' in context.exception.message)

        nodes = OrgTree().all_leaves_below_id(101)
        self.assertEqual(1, len(nodes))

    def test_deeper_org_tree(self):
        self.deepen_org_tree()
        leaves = OrgTree().all_leaves_below_id(102)
        self.assertTrue(len(leaves) == 2)
        self.assertTrue(10032 in leaves)
        self.assertTrue(10031 in leaves)

    def test_top_names(self):
        self.deepen_org_tree()
        self.assertEqual({'101', '102'}, set(OrgTree().top_level_names()))

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
        self.assertEqual(len(leaves), 3)
        self.assertTrue(1001 in leaves)
        self.assertTrue(10031 in leaves)
        self.assertTrue(10032 in leaves)

    def test_all_leaves(self):
        # can we get a list of just the leaf orgs
        self.deepen_org_tree()
        leaves = OrgTree().all_leaf_ids()
        self.assertEqual(len(leaves), 3)
        for i in (1001, 10031, 10032):
            self.assertTrue(i in leaves)

    def test_here_and_below_id(self):
        self.deepen_org_tree()
        nodes = OrgTree().here_and_below_id(102)
        self.assertEqual(len(nodes), 4)
        for i in (102, 1002, 10031, 10032):
            self.assertTrue(i in nodes)

    def test_visible_patients_on_none(self):
        # Add none of the above to users orgs
        self.test_user.organizations.append(Organization.query.get(0))
        self.promote_user(role_name=ROLE.STAFF)
        self.test_user = db.session.merge(self.test_user)

        patients_list = OrgTree().visible_patients(self.test_user)
        self.assertEqual(len(patients_list), 0)

    def test_user_org_get(self):
        self.bless_with_basics()
        self.test_user = db.session.merge(self.test_user)
        expected = [
            Reference.organization(o.id).as_fhir()
            for o in self.test_user.organizations]
        self.login()
        rv = self.client.get('/api/user/{}/organization'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEqual(rv.json['organizations'], expected)

    def test_user_org_post(self):
        self.shallow_org_tree()
        self.prep_org_w_identifier()
        data = {'organizations': [
            {'reference': 'api/organization/123-45?system={}'.format(US_NPI)},
            {'reference': 'api/organization/1001'}
        ]}
        self.login()
        rv = self.client.post(
            '/api/user/{}/organization'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))

        self.assert200(rv)
        self.assertEqual(len(rv.json['organizations']), 2)
