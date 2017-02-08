"""Model classes for organizations and related entities.

Designed around FHIR guidelines for representation of organizations, locations
and healthcare services which are used to describe hospitals and clinics.
"""
from sqlalchemy import UniqueConstraint, and_
from flask import url_for

import address
from ..extensions import db
from .fhir import CodeableConcept, FHIR_datetime
from .identifier import Identifier
import reference
from .telecom import Telecom


class Organization(db.Model):
    """Model representing a FHIR organization

    Organizations represent a collection of people that have come together
    to achieve an objective.  As an example, all the healthcare
    services provided by the same university hospital will belong to
    the organization representing said university hospital.

    Organizations can reference other organizations via the 'partOf_id',
    where children name their parent organization id.

    """
    __tablename__ = 'organizations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    type_id = db.Column(db.ForeignKey('codeable_concepts.id',
                                      ondelete='cascade'))
    partOf_id = db.Column(db.ForeignKey('organizations.id'))

    addresses = db.relationship('Address', lazy='dynamic',
            secondary="organization_addresses")
    identifiers = db.relationship('Identifier', lazy='dynamic',
            secondary="organization_identifiers")
    type = db.relationship('CodeableConcept', cascade="save-update")

    def __str__(self):
        part_of = 'partOf {} '.format(self.partOf_id) if self.partOf_id else ''
        addresses = '; '.join([str(a) for a in self.addresses])

        return 'Organization {0.name} {0.type} {0.phone} {0.email} '.format(
                self) + part_of + addresses

    @classmethod
    def from_fhir(cls, data):
        org = cls()
        return org.update_from_fhir(data)

    def update_from_fhir(self, data):
        if 'id' in data:
            self.id = data['id']
        if 'name' in data:
            self.name = data['name']
        if 'telecom' in data:
            telecom = Telecom.from_fhir(data['telecom'])
            self.phone = telecom.phone
            self.email = telecom.email
        if 'address' in data:
            for addr in data['address']:
                self.addresses.append(address.Address.from_fhir(addr))
        if 'type' in data:
            self.type = CodeableConcept.from_fhir(data['type'])
        if 'partOf' in data:
            self.partOf_id = reference.Reference.parse(data['partOf']).id
        if 'identifier' in data:
            for id in data['identifier']:
                identifier = Identifier.from_fhir(id).add_if_not_found()
                if identifier not in self.identifiers.all():
                    self.identifiers.append(identifier)
        return self

    def as_fhir(self):
        d = {}
        d['resourceType'] = 'Organization'
        d['id'] = self.id
        d['name'] = self.name
        telecom = Telecom(email=self.email, phone=self.phone)
        d['telecom'] = telecom.as_fhir()
        if self.addresses:
            d['address'] = []
        for addr in self.addresses:
            d['address'].append(addr.as_fhir())
        if self.type:
            d['type'] = self.type.as_fhir()
        if self.partOf_id:
            d['partOf'] = reference.Reference.organization(
                self.partOf_id).as_fhir()
        if self.identifiers:
            d['identifier'] = []
        for id in self.identifiers:
            d['identifier'].append(id.as_fhir())
        return d

    @classmethod
    def generate_bundle(cls):
        """Generate a FHIR bundle of existing orgs ordered by ID"""

        query = Organization.query.order_by(Organization.id)
        orgs = [o.as_fhir() for o in query]

        bundle = {
            'resourceType':'Bundle',
            'updated':FHIR_datetime.now(),
            'total':len(orgs),
            'type': 'searchset',
            'link': {
                'rel':'self',
                'href':url_for(
                    'org_api.organization_list', _external=True),
            },
            'entry':orgs,
        }
        return bundle


class UserOrganization(db.Model):
    """link table for users (n) : organizations (n)"""
    __tablename__ = 'user_organizations'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='cascade'), nullable=False)
    user_id = db.Column(db.ForeignKey(
        'users.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint('user_id', 'organization_id',
        name='_user_organization'),)

    organization = db.relationship('Organization')

class OrganizationAddress(db.Model):
    """link table for organization : n addresses"""
    __tablename__ = 'organization_addresses'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='cascade'), nullable=False)
    address_id = db.Column(db.ForeignKey(
        'addresses.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint('organization_id', 'address_id',
        name='_organization_address'),)


class OrganizationIdentifier(db.Model):
    """link table for organization : n identifiers"""
    __tablename__ = 'organization_identifiers'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='cascade'), nullable=False)
    identifier_id = db.Column(db.ForeignKey(
        'identifiers.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint('organization_id', 'identifier_id',
        name='_organization_identifier'),)


class OrgNode(object):
    """Node in tree of organizations - used by org tree

    Simple tree implementation to house organizations in a hierarchical
    structure.  One root - any number of nodes at each tier.  The organization
    identifiers (integers referring to the database primary key) are used
    as reference keys.

    """
    def __init__(self, id, parent = None, children = None):
        self.id = id  # root node alone has id = None
        self.parent = parent
        self.children = children if children else {}
        if self.id is None:
            assert self.parent is None

    def insert(self, id, partOf_id=None):
        """Insert new nodes into the org tree

        Designed for this special organizaion purpose, we expect the
        tree is built from the top (root) down, so no rebalancing is
        necessary.

        :param id: of organizaiton to insert
        :param partOf_id: if organization has a parent - its identifier
        :returns: the newly inserted node

        """
        if id is None:
            # Only allowed on root node - building top down, don't allow
            raise ValueError("only root node can have null id")
        if self.id == id:
            # Referring to self, don't allow
            raise ValueError("{} already in tree".format(id))
        if self.id == partOf_id:
            # Adding child, confirm it's new
            assert id not in self.children
            node = OrgNode(id=id, parent=self)
            self.children[id] = node
            return node
        else:
            # Could be adding to root node, confirm it's top level
            assert(self.id is None and partOf_id is None)
            node = OrgNode(id=id, parent=self)
            assert id not in self.children
            self.children[id] = node
            return node

    def top_level(self):
        """Lookup top_level organization id from the given node

        Use OrgTree.find() to locate starter node, if necessary

        """
        if not self.parent:
            raise ValueError('popped off the top')
        if self.parent.id is None:
            return self.id
        return self.parent.top_level()


class OrgTree(object):
    """In-memory organizations tree for hierarchy and structure

    Organizations may define a 'partOf' in the database records to describe
    where the organization fits in a hierarchy.  As there may be any
    number of organization tiers, and the need exists to lookup where
    an organiztion fits in this hiearchy.  For example, needing to lookup
    the top level organization for any node, or all the organizations at or
    below a level for permission issues. etc.

    This singleton class will build up the tree when it's first needed (i.e.
    lazy load).

    Note, the root of the tree is a dummy object, so the first tier can be
    multiple `top-level` organizations.

    """
    root = None
    lookup_table = None

    def __init__(self):
        # Maintain a singleton root object and lookup_table
        if not OrgTree.root:
            OrgTree.root = OrgNode(id=None)
            OrgTree.lookup_table = {}
            self.populate_tree()

    @classmethod
    def invalidate_cache(cls):
        """Invalidate cache on org changes"""
        cls.root = None

    def populate_tree(self):
        """Recursively build tree from top down"""
        if self.root.children:  # Done if already populated
            return

        def add_descendents(node):
            partOf_id = node.id
            for org in Organization.query.filter(and_(
                Organization.id != 0,  # none of the above doesn't apply
                Organization.partOf_id == partOf_id)):
                new_node = node.insert(id=org.id, partOf_id=partOf_id)
                assert org.id not in self.lookup_table
                self.lookup_table[org.id] = new_node
                if Organization.query.filter(
                    Organization.partOf_id == new_node.id).count():
                    add_descendents(new_node)

        # Add top level orgs first, recurse on down
        add_descendents(self.root)

    def find(self, organization_id):
        """Locates and returns node in OrgTree for given organization_id

        :param organization_id: primary key of organization to locate
        :return: OrgNode from OrgTree
        :raises: ValueError if not found - unexpected

        """
        organization_id = int(organization_id)
        if organization_id not in self.lookup_table:
            raise ValueError("{} not found in OrgTree".format(organization_id))
        return self.lookup_table[organization_id]

    def all_top_level_ids(self):
        """Return list of all top level organization identifiers"""
        return self.root.children.keys()

    def all_leaf_ids(self):
        nodes = set()
        for id in self.all_top_level_ids():
            nodes.update(self.all_leaves_below_id(id))
        return list(nodes)

    def all_leaves_below_id(self, organization_id):
        """Given org at arbitrary level, return list of leaf nodes below it"""
        arb = self.find(organization_id)

        def fetch_leaves(node):
            stack = [node]
            while stack:
                node = stack.pop()
                if not node.children:
                    yield node.id
                for child_node in node.children.values():
                    stack.append(child_node)

        return list(fetch_leaves(arb))

    def here_and_below_id(self, organization_id):
        """Given org at arbitrary level, return list at and below"""
        arb = self.find(organization_id)

        def fetch_nodes(node):
            stack = [node]
            while stack:
                node = stack.pop()
                yield node.id
                for id, child_node in node.children.items():
                    stack.append(child_node)

        return list(fetch_nodes(arb))

    def at_or_below_ids(self, organization_id, other_organizations):
        """Check if the other_organizations are at or below given organization

        :param organization_id: effective parent to check against
        :param other_organizations: iterable of organization_ids as potential
            children.

        :return: True if any org in other_organizations is equal to the
            given organization_id, or a child of it.

        """
        ## work through list - shortcircuit out if a qualified node is found
        for other_organization_id in other_organizations:
            if organization_id == other_organization_id:
                return True
            children = self.here_and_below_id(organization_id)
            if other_organization_id in children:
                return True


def add_static_organization():
    """Insert special `none of the above` org at index 0"""
    existing = Organization.query.get(0)
    if not existing:
        db.session.add(Organization(id=0, name='none of the above'))
