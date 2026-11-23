"""Unit test module for organization model"""

from builtins import map
from datetime import datetime, timedelta
import json
import os
from urllib.parse import quote_plus

from flask_webtest import SessionScope
import pytest

from portal.extensions import db
from portal.models.coding import Coding
from portal.models.identifier import Identifier
from portal.models.locale import LocaleConstants
from portal.models.organization import (
    LocaleExtension,
    Organization,
    OrganizationIdentifier,
    OrganizationResearchProtocol,
    OrgTree,
    ResearchProtocolExtension,
    org_restriction_by_role,
)
from portal.models.reference import Reference
from portal.models.research_protocol import ResearchProtocol
from portal.models.research_study import ResearchStudy
from portal.models.role import ROLE
from portal.system_uri import (
    IETF_LANGUAGE_TAG,
    PRACTICE_REGION,
    SHORTCUT_ALIAS,
    SHORTNAME_ID,
    TRUENTH_RP_EXTENSION,
    US_NPI,
)
from tests import TEST_USER_ID


def item_from_extensions(extensions, item_url):
    """test helper to extract and return just the requested extension"""
    for ext in extensions:
        if ext['url'] == item_url:
            return ext


def test_from_fhir():
    with (open(
        os.path.join(
            os.path.dirname(__file__),
            'organization-example-f001-burgers.json'),
        'r')
    ) as fhir_data:
        data = json.load(fhir_data)

    # prepopulate database with matching locale
    Coding.from_fhir(
        {'code': 'en_AU', 'display': 'Australian English',
         'system': IETF_LANGUAGE_TAG})
    org = Organization.from_fhir(data)
    assert org.addresses[0].line1 == data['address'][0]['line'][0]
    assert org.addresses[1].line1 == data['address'][1]['line'][0]
    assert org.name == data['name']
    assert org.phone == "022-655 2300"
    assert org.use_specific_codings
    assert org.race_codings
    assert not org.ethnicity_codings
    assert org.locales.count() == 1
    assert org.default_locale == "en_AU"
    assert org._timezone == "US/Pacific"


def test_from_fhir_partOf():
    # prepopulate database with parent organization
    parent = Organization(id=101, name='fake parent reference')
    with SessionScope(db):
        db.session.add(parent)
        db.session.commit()
    parent = db.session.merge(parent)
    parent_id = parent.id

    with (open(
        os.path.join(
            os.path.dirname(__file__),
            'organization-example-f002-burgers-card.json'),
        'r')
    ) as fhir_data:
        data = json.load(fhir_data)

    # remove the id from the file - doesn't play well with ours
    data.pop('id')
    org = Organization.from_fhir(data)

    assert org.addresses[0].line1 == data['address'][0]['line'][0]
    assert org.name == data['name']
    assert org.phone == "022-655 2320"
    assert org.partOf_id == parent_id

    # confirm we can store
    with SessionScope(db):
        db.session.add(org)
        db.session.commit()
    org = db.session.merge(org)
    assert org.id
    assert org.partOf_id == parent_id


def test_timezone_inheritance():
    parent = Organization(id=101, name='parentOrg')
    org = Organization(id=102, name='org', partOf_id=101)

    # test that with no timezones set, defaults to UTC
    with SessionScope(db):
        db.session.add(parent)
        db.session.add(org)
        db.session.commit()
    parent, org = map(db.session.merge, (parent, org))
    assert org.timezone == 'UTC'
    tz_ext = item_from_extensions(
        org.as_fhir()['extension'],
        'http://hl7.org/fhir/StructureDefinition/user-timezone')
    assert tz_ext['timezone'] == 'UTC'

    # test that timezone-less child org inherits from parent
    parent.timezone = 'Asia/Tokyo'
    with SessionScope(db):
        db.session.add(parent)
        db.session.commit()
    parent, org = map(db.session.merge, (parent, org))
    assert org.timezone == 'Asia/Tokyo'
    tz_ext = item_from_extensions(
        org.as_fhir()['extension'],
        'http://hl7.org/fhir/StructureDefinition/user-timezone')
    assert tz_ext['timezone'] == 'Asia/Tokyo'

    # test that child org with timezone does NOT inherit from parent
    org.timezone = 'Europe/Rome'
    with SessionScope(db):
        db.session.add(org)
        db.session.commit()
    org = db.session.merge(org)
    assert org.timezone == 'Europe/Rome'
    tz_ext = item_from_extensions(
        org.as_fhir()['extension'],
        'http://hl7.org/fhir/StructureDefinition/user-timezone')
    assert tz_ext['timezone'] == 'Europe/Rome'


def test_as_fhir():
    org = Organization(name='Homer\'s Hospital')
    org.use_specific_codings = True
    org.race_codings = False
    data = org.as_fhir()
    assert org.name == data['name']
    assert data['use_specific_codings']
    assert not data['race_codings']


def test_multiple_rps_in_fhir():
    with SessionScope(db):
        db.session.add(ResearchStudy(title='base study'))
        db.session.commit()
    rs_id = ResearchStudy.query.with_entities(ResearchStudy.id).first()
    yesterday = datetime.utcnow() - timedelta(days=1)
    lastyear = datetime.utcnow() - timedelta(days=365)
    org = Organization(name='Testy')
    rp1 = ResearchProtocol(name='rp1', research_study_id=rs_id)
    rp2 = ResearchProtocol(name='yesterday', research_study_id=rs_id)
    rp3 = ResearchProtocol(name='last year', research_study_id=rs_id)
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
    assert org.name == data['name']
    rps = [
        extension for extension in data['extension']
        if extension['url'] == ResearchProtocolExtension.extension_url]

    assert len(rps) == 1
    assert len(rps[0]['research_protocols']) == 3

    # confirm the order is descending in the custom accessor method
    results = [
        (rp, retired) for rp, retired in
        org.rps_w_retired(research_study_id=rs_id)]
    assert [(rp1, None), (rp2, yesterday), (rp3, lastyear)] == results


def test_organization_get(test_user_login, client):
    org = Organization(name='test')
    with SessionScope(db):
        db.session.add(org)
        db.session.commit()
    org = db.session.merge(org)

    # use api to obtain FHIR
    response = client.get('/api/organization/{}'.format(org.id))
    assert response.status_code == 200


def test_organization_get_by_identifier(test_user_login, client):
    org_id_system = "http://test/system"
    org_id_value = "testval"
    org = Organization(name='test', id=999)
    ident = Identifier(id=99, system=org_id_system, value=org_id_value)
    org_ident = OrganizationIdentifier(
        organization_id=999, identifier_id=99)
    with SessionScope(db):
        db.session.add(org)
        db.session.add(ident)
        db.session.commit()
        db.session.add(org_ident)
        db.session.commit()

    # use api to obtain FHIR
    response = client.get(
        '/api/organization?system={system}&value={value}'.format(
            system=quote_plus(org_id_system), value=org_id_value))
    assert response.status_code == 200
    assert response.json['total'] == 1
    assert response.json['entry'][0]['id'] == 999

    # use alternative API to obtain organization
    response = client.get(
        '/api/organization/{value}?system={system}'.format(
            system=quote_plus(org_id_system), value=org_id_value))
    assert response.status_code == 200
    fetched = Organization.from_fhir(response.json)
    org = db.session.merge(org)
    assert org.id == fetched.id
    assert org.name == fetched.name


def test_org_missing_identifier(
        client, initialized_patient_logged_in):
    # should get 404 w/o finding a match
    response = client.get(
        '/api/organization/{value}?system={system}'.format(
            system=quote_plus('http://nonsense.org'), value='123-45'))
    assert response.status_code == 404


def test_organization_list(
        client, initialized_patient_logged_in):
    count = Organization.query.count()

    # use api to obtain FHIR bundle
    response = client.get('/api/organization')
    assert response.status_code == 200
    bundle = response.json
    assert bundle['resourceType'] == 'Bundle'
    assert len(bundle['entry']) == count


def test_organization_search(
        shallow_org_tree, client, test_user_login):
    count = Organization.query.count()
    assert count > 1

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
    response = client.get('/api/organization?state=NY')
    assert response.status_code == 200
    bundle = response.json
    assert bundle['resourceType'] == 'Bundle'
    assert len(bundle['entry']) == 1


def test_organization_inheritence_search(
        test_user_login, deepen_org_tree, client):
    # Region at top should apply to leaves
    count = Organization.query.count()
    assert count > 3

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
    response = client.get('/api/organization?state=NY')
    assert response.status_code == 200
    bundle = response.json
    assert bundle['resourceType'] == 'Bundle'
    assert len(bundle['entry']) == 3

    # add filter to restrict to just the leaves
    response = client.get('/api/organization?state=NY&filter=leaves')
    assert response.status_code == 200
    bundle = response.json
    assert bundle['resourceType'] == 'Bundle'
    assert len(bundle['entry']) == 2


def test_organization_filter(
        test_user_login, deepen_org_tree, client):
    # Filter w/o a search term
    count = Organization.query.count()
    assert count > 6

    # Filter w/o search should give a short list of orgs
    response = client.get('/api/organization?filter=leaves')
    assert response.status_code == 200
    bundle = response.json
    assert bundle['resourceType'] == 'Bundle'

    # one organization is music_org
    # other three came from deepen_org_tree
    assert len(bundle['entry']) == 4


def test_organization_put(
        promote_user, test_user_login, client):
    promote_user(role_name=ROLE.ADMIN.value)
    with (open(
        os.path.join(
            os.path.dirname(__file__),
            'organization-example-f001-burgers.json'),
        'r')
    ) as fhir_data:
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

    # prepopulate database with matching locale
    Coding.from_fhir({
        'code': 'en_AU',
        'display': 'Australian English',
        'system': "urn:ietf:bcp:47"})

    response = client.put(
        '/api/organization/{}'.format(org_id),
        content_type='application/json', data=json.dumps(data))
    assert response.status_code == 200

    # Pull the updated db entry
    org = Organization.query.get(org_id)
    assert org.addresses[0].line1 == data['address'][0]['line'][0]
    assert org.addresses[1].line1 == data['address'][1]['line'][0]
    assert org.name == data['name']
    assert org.phone == "022-655 2300"


def test_organization_put_update(
        promote_user, test_user_login, client):
    # confirm unmentioned fields persist
    promote_user(role_name=ROLE.ADMIN.value)

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

    response = client.put(
        '/api/organization/{}'.format(org_id),
        content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 200

    # Pull the updated db entry
    org = Organization.query.get(org_id)
    en_AU = db.session.merge(en_AU)

    # Confirm all the unmentioned entries survived
    assert org.phone == '800-800-5665'
    assert org.default_locale == 'en_AU'
    assert org.locales[0] == en_AU
    assert org.timezone == 'US/Pacific'


def test_org_rp_inheritance(initialized_with_org):
    fhir = initialized_with_org.as_fhir()
    assert fhir['resourceType'] == 'Organization'
    rp_ext = item_from_extensions(fhir['extension'], TRUENTH_RP_EXTENSION)
    assert rp_ext['research_protocols'][0]['research_study_id'] == 0

    # Add child org, w/o a research protocol to pick up parent value
    child = Organization(name='child', partOf_id=initialized_with_org.id)
    with SessionScope(db):
        db.session.add(child)
        db.session.commit()
    child = db.session.merge(child)
    child_fhir = child.as_fhir()
    rp_ext = item_from_extensions(
        child_fhir['extension'], TRUENTH_RP_EXTENSION)
    assert 'research_protocols' not in rp_ext
    inherited = child.as_fhir(include_empties=False, include_inherited=True)
    rp_ext = item_from_extensions(
        inherited['extension'], TRUENTH_RP_EXTENSION)
    assert 'research_protocols' in rp_ext


def test_organization_extension_update(
        promote_user, test_user_login, client):
    # confirm clearing one of several extensions works
    promote_user(role_name=ROLE.ADMIN.value)

    en_AU = LocaleConstants().AustralianEnglish

    # Populate db with complete org, and set many fields
    org = Organization(
        name='test', phone='800-800-5665', timezone='US/Pacific')
    org.identifiers.append(Identifier(
        value='state:NY', system=PRACTICE_REGION))
    org.locales.append(en_AU)
    org.default_locale = 'en_AU'
    rp = ResearchProtocol(name='rp1', research_study_id=0)

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

    response = client.put(
        '/api/organization/{}'.format(org_id),
        content_type='application/json',
        data=json.dumps(input))
    assert response.status_code == 200

    # Pull the updated db entry
    org = Organization.query.get(org_id)
    en_AU = db.session.merge(en_AU)

    # Confirm all the unmentioned entries survived
    assert org.phone == '800-800-5665'
    assert org.default_locale == 'en_AU'
    assert org.locales.count() == 0
    assert org.timezone == 'US/Pacific'
    assert org.research_protocol(
        research_study_id=0, as_of_date=datetime.utcnow()).id == rp_id

    # Confirm empty extension isn't included in result
    results = response.json
    for e in results['extension']:
        assert 'url' in e
        assert len(e.keys()) > 1


def test_organization_post(
        promote_user, test_user_login, client):
    with (open(
        os.path.join(
            os.path.dirname(__file__),
            'organization-example-f002-burgers-card.json'),
        'r')
    ) as fhir_data:
        data = json.load(fhir_data)

    # the 002-burgers-card org refers to another - should fail
    # prior to adding the parent (partOf) org
    promote_user(role_name=ROLE.ADMIN.value)
    response = client.post(
        '/api/organization', content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 400


def test_organization_delete(
        shallow_org_tree, promote_user,
        test_user_login, client):
    (org1_id, org1_name), (org2_id, org2_name) = [
        (org.id, org.name) for org in Organization.query.filter(
            Organization.id > 0).limit(2)]

    # use api to delete one and confirm the other remains
    promote_user(role_name=ROLE.ADMIN.value)
    response = client.delete('/api/organization/{}'.format(org2_id))
    assert response.status_code == 200
    assert Organization.query.get(org2_id) is None
    orgs = Organization.query.all()
    names = [o.name for o in orgs]
    assert 'none of the above' in names
    assert org1_name in names


def test_organization_identifiers(
        shallow_org_tree, initialized_db):
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
    assert org.identifiers.count() == before + 2


def test_organization_identifiers_update(
        shallow_org_tree, promote_user, test_user_login,
        client, initialized_db):
    with open(os.path.join(
        os.path.dirname(__file__),
        'organization-example-gastro.json'), 'r'
    ) as fhir_data:
        data = json.load(fhir_data)
    promote_user(role_name=ROLE.ADMIN.value)
    before = Organization.query.count()
    response = client.post(
        '/api/organization', content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 200
    assert Organization.query.count() == before + 1

    # the gastro file contains a single identifier - add
    # a second one and PUT, expecting we get two total

    alias = Identifier(system=SHORTCUT_ALIAS, value='foobar',
                       use='secondary')
    org = Organization.query.filter_by(name='Gastroenterology').one()
    data['identifier'].append(alias.as_fhir())
    response = client.put(
        '/api/organization/{}'.format(org.id),
        content_type='application/json', data=json.dumps(data))
    assert response.status_code == 200

    # obtain the org from the db, check the identifiers
    org = Organization.query.filter_by(name='Gastroenterology').one()
    assert 2 == org.identifiers.count()


def test_shortname(shallow_org_tree):
    shorty = Identifier(system=SHORTNAME_ID, value='shorty')
    org = Organization.query.filter(Organization.id > 0).first()
    # prior to adding shortname, should just get org name
    assert org.name == org.shortname

    org.identifiers.append(shorty)
    with SessionScope(db):
        db.session.commit()
    org = db.session.merge(org)
    # after, should get the shortname
    assert org.shortname == 'shorty'


def test_org_tree_nodes(shallow_org_tree):
    with pytest.raises(ValueError) as context:
        OrgTree().all_leaves_below_id(0)  # none of the above
    assert 'not found' in str(context.value)

    nodes = OrgTree().all_leaves_below_id(101)
    assert 1 == len(nodes)


def test_deeper_org_tree(deepen_org_tree):
    leaves = OrgTree().all_leaves_below_id(102)
    assert len(leaves) == 2
    assert 10032 in leaves
    assert 10031 in leaves


def test_at_and_above(deepen_org_tree):
    results = OrgTree().at_and_above_ids(10032)
    assert len(results) == 3


def test_top_names(deepen_org_tree):
    assert {'101', '102'} == set(OrgTree().top_level_names())


def test_roots(deepen_org_tree):
    # Given two orgs on the same branch of tree and one from another
    # branch should result in just two root nodes
    orgs_on_branch = (
        Organization.query.get(102), Organization.query.get(10031),
        Organization.query.get(1001))
    assert ({Organization.query.get(101), Organization.query.get(102)}
            == OrgTree().find_top_level_orgs(orgs_on_branch))


def test_staff_leaves(deepen_org_tree, promote_user, test_user):
    # test staff with several org associations produces correct list
    # Make staff with org associations at two levels
    promote_user(role_name=ROLE.STAFF.value)
    test_user = db.session.merge(test_user)

    orgs = Organization.query.filter(Organization.id.in_((101, 102)))
    for o in orgs:
        test_user.organizations.append(o)
    with SessionScope(db):
        db.session.commit()
    test_user = db.session.merge(test_user)

    # Should now find children of 101 (1001) and leaf children
    # of 102 (10031, 10032) for total of 3 leaf nodes
    leaves = test_user.leaf_organizations()
    assert len(leaves) == 3
    assert 1001 in leaves
    assert 10031 in leaves
    assert 10032 in leaves


def test_all_leaves(deepen_org_tree):
    # can we get a list of just the leaf orgs
    leaves = OrgTree().all_leaf_ids()
    assert len(leaves) == 3
    for i in (1001, 10031, 10032):
        assert i in leaves


def test_here_and_below_id(deepen_org_tree):
    nodes = OrgTree().here_and_below_id(102)
    assert len(nodes) == 4
    for i in (102, 1002, 10031, 10032):
        assert i in nodes


def test_visible_orgs_on_none(test_user, promote_user):
    # Add none of the above to users orgs
    test_user.organizations.append(Organization.query.get(0))
    promote_user(role_name=ROLE.STAFF.value)
    test_user = db.session.merge(test_user)

    org_list = org_restriction_by_role(test_user, None)
    assert len(org_list) == 0


def test_user_org_get(
        bless_with_basics, test_user, test_user_login, client):
    test_user = db.session.merge(test_user)
    expected = [
        Reference.organization(o.id).as_fhir()
        for o in test_user.organizations]
    response = client.get('/api/user/{}/organization'.format(
        TEST_USER_ID))
    assert response.status_code == 200
    assert response.json['organizations'] == expected


def test_user_org_post(
        shallow_org_tree, prep_org_w_identifier, test_user_login, client):
    data = {'organizations': [
        {'reference': 'api/organization/123-45?system={}'.format(US_NPI)},
        {'reference': 'api/organization/1001'}
    ]}
    response = client.post(
        '/api/user/{}/organization'.format(TEST_USER_ID),
        content_type='application/json',
        data=json.dumps(data))

    assert response.status_code == 200
    assert len(response.json['organizations']) == 2


def test_user_org_bogus_identifier(
        shallow_org_tree, test_user_login, client):
    data = {'organizations': [
        {'reference':
         'api/organization/123-45?system={}'.format(US_NPI[:-1])}
    ]}
    response = client.post(
        '/api/user/{}/organization'.format(TEST_USER_ID),
        content_type='application/json',
        data=json.dumps(data))

    assert response.status_code == 400


def test_user_org_invalid_timezone_post(
        shallow_org_tree, test_user_login, client):
    # only one org in list can be marked with `apply_to_user`
    data = {'organizations': [
        {'reference': 'api/organization/102', 'timezone': "apply_to_user"},
        {'reference': 'api/organization/1001', 'timezone': "apply_to_user"}
    ]}
    response = client.post(
        '/api/user/{}/organization'.format(TEST_USER_ID),
        content_type='application/json',
        data=json.dumps(data))

    assert response.status_code == 400


def test_user_org_apply_defaults(
        shallow_org_tree, test_user, test_user_login, client):
    # apply org timezone and language defaults to user
    sib = Organization.query.get(102)
    sib.timezone = 'Europe/Rome'
    parent = Organization.query.get(101)
    parent.default_locale = 'en_AU'
    with SessionScope(db):
        db.session.commit()

    data = {'organizations': [
        {'reference': 'api/organization/102', 'timezone': "apply_to_user"},
        {'reference': 'api/organization/1001', 'language': "apply_to_user"}
    ]}
    response = client.post(
        '/api/user/{}/organization'.format(TEST_USER_ID),
        content_type='application/json',
        data=json.dumps(data))

    assert response.status_code == 200
    user = db.session.merge(test_user)
    assert user.timezone == 'Europe/Rome'
    assert user.locale_code == 'en_AU'
