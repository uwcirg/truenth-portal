"""Model classes for organizations and related entities.

Designed around FHIR guidelines for representation of organizations, locations
and healthcare services which are used to describe hospitals and clinics.
"""
from flask import current_app, url_for
from sqlalchemy import UniqueConstraint, and_
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized

from . import address
from ..database import db
from ..date_tools import FHIR_datetime
from ..dict_tools import strip_empties
from ..system_uri import IETF_LANGUAGE_TAG, SHORTNAME_ID, TRUENTH_RP_EXTENSION
from .app_text import (
    ConsentByOrg_ATMA,
    UndefinedAppText,
    UnversionedResource,
    VersionedResource,
    app_text,
)
from .codeable_concept import CodeableConcept
from .coding import Coding
from .extension import CCExtension, TimezoneExtension
from .fhir import bundle_results
from .identifier import Identifier
from .reference import Reference
from .research_protocol import ResearchProtocol
from .role import ROLE, Role
from .telecom import ContactPoint, Telecom

USE_SPECIFIC_CODINGS_MASK = 0b0001
RACE_CODINGS_MASK = 0b0010
ETHNICITY_CODINGS_MASK = 0b0100
INDIGENOUS_CODINGS_MASK = 0b1000


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
    phone_id = db.Column(
        db.Integer, db.ForeignKey('contact_points.id', ondelete='cascade'))
    type_id = db.Column(db.ForeignKey(
        'codeable_concepts.id', ondelete='cascade'))
    partOf_id = db.Column(db.ForeignKey('organizations.id'))
    coding_options = db.Column(db.Integer, nullable=False, default=0)
    default_locale_id = db.Column(db.ForeignKey('codings.id'))
    _timezone = db.Column('timezone', db.String(20))

    addresses = db.relationship(
        'Address', lazy='dynamic', secondary="organization_addresses")
    identifiers = db.relationship(
        'Identifier', lazy='dynamic', secondary="organization_identifiers")
    locales = db.relationship(
        'Coding', lazy='dynamic', secondary="organization_locales")
    _phone = db.relationship(
        'ContactPoint', foreign_keys=phone_id, cascade="save-update")
    research_protocols = association_proxy(
        "organization_research_protocols", "research_protocol",
        creator=lambda rp: OrganizationResearchProtocol(research_protocol=rp))
    type = db.relationship('CodeableConcept', cascade="save-update")

    def __init__(self, **kwargs):
        self.coding_options = 14
        super(Organization, self).__init__(**kwargs)

    def __str__(self):
        return 'Organization({0.id}) {0.name}'.format(self)

    @hybrid_property
    def use_specific_codings(self):
        return self.coding_options & USE_SPECIFIC_CODINGS_MASK

    @use_specific_codings.setter
    def use_specific_codings(self, value):
        if value:
            self.coding_options |= USE_SPECIFIC_CODINGS_MASK
        else:
            self.coding_options &= ~USE_SPECIFIC_CODINGS_MASK

    @hybrid_property
    def race_codings(self):
        if self.use_specific_codings:
            return self.coding_options & RACE_CODINGS_MASK
        elif self.partOf_id:
            org = Organization.query.get(self.partOf_id)
            return org.race_codings
        else:
            return True

    @race_codings.setter
    def race_codings(self, value):
        if value:
            self.coding_options |= RACE_CODINGS_MASK
        else:
            self.coding_options &= ~RACE_CODINGS_MASK

    @hybrid_property
    def ethnicity_codings(self):
        if self.use_specific_codings:
            return self.coding_options & ETHNICITY_CODINGS_MASK
        elif self.partOf_id:
            org = Organization.query.get(self.partOf_id)
            return org.ethnicity_codings
        else:
            return True

    @ethnicity_codings.setter
    def ethnicity_codings(self, value):
        if value:
            self.coding_options |= ETHNICITY_CODINGS_MASK
        else:
            self.coding_options &= ~ETHNICITY_CODINGS_MASK

    @hybrid_property
    def indigenous_codings(self):
        if self.use_specific_codings:
            return self.coding_options & INDIGENOUS_CODINGS_MASK
        elif self.partOf_id:
            org = Organization.query.get(self.partOf_id)
            return org.indigenous_codings
        else:
            return True

    @indigenous_codings.setter
    def indigenous_codings(self, value):
        if value:
            self.coding_options |= INDIGENOUS_CODINGS_MASK
        else:
            self.coding_options &= ~INDIGENOUS_CODINGS_MASK

    @property
    def phone(self):
        if self._phone:
            return self._phone.value

    @phone.setter
    def phone(self, val):
        if self._phone:
            self._phone.value = val
        else:
            self._phone = ContactPoint(system='phone', use='work', value=val)

    @property
    def default_locale(self):
        coding = None
        org = self
        if org.default_locale_id:
            coding = Coding.query.get(org.default_locale_id)
        while org.partOf_id and not coding:
            org = Organization.query.get(org.partOf_id)
            if org.default_locale_id:
                coding = Coding.query.get(org.default_locale_id)
        if coding:
            return coding.code

    @default_locale.setter
    def default_locale(self, value):
        if not value:
            self.default_locale_id = None
        else:
            coding = Coding.query.filter_by(
                system=IETF_LANGUAGE_TAG, code=value).first()
            if not coding:
                raise ValueError(
                    "Can't find locale code {value} - constrained to "
                    "pre-existing values in the {system} system".format(
                        value=value, system=IETF_LANGUAGE_TAG))
            self.default_locale_id = coding.id

    @property
    def shortname(self):
        """Return shortname identifier if found, else the org name"""
        shortnames = [
            id for id in self.identifiers if id.system == SHORTNAME_ID]
        if len(shortnames) > 1:
            raise ValueError(
                "multiple shortname identifiers found for {}".format(self))
        return shortnames[0].value if shortnames else self.name

    @property
    def timezone(self):
        org = self
        if org._timezone:
            return org._timezone
        while org.partOf_id:
            org = Organization.query.get(org.partOf_id)
            if org._timezone:
                return org._timezone
        # return 'UTC' if no parent inheritances found
        return 'UTC'

    @timezone.setter
    def timezone(self, value):
        self._timezone = value

    def rps_w_retired(self, research_study_id, consider_parents=False):
        """accessor to collate research protocols and retired_as_of values

        The SQLAlchemy association proxy doesn't provide easy access to
        `intermediary` table data - i.e. columns in the link table between
        a many:many association.  This accessor collates the value stored
        in the intermediary table, `retired_as_of` with the research protocols
        for this organization.

        :param research_study_id: the study being processed, or "all"
        :param consider_parents: if set and the org doesn't have an
         associated RP, continue up the org hiearchy till one is found.

        :returns: ready query for use in iteration or count or other methods.
         Query will produce a list of tuples (ResearchProtocol, retired_as_of)
         associated with the organization, ordered by `retired_as_of` dates
         with nulls last.

        """
        def fetch_for_org(org_id):
            items = OrganizationResearchProtocol.query.join(
                ResearchProtocol).filter(
                OrganizationResearchProtocol.research_protocol_id ==
                ResearchProtocol.id).filter(
                OrganizationResearchProtocol.organization_id == org_id
            ).with_entities(
                ResearchProtocol,
                OrganizationResearchProtocol.retired_as_of).order_by(
                OrganizationResearchProtocol.retired_as_of.desc())

            if research_study_id != "all":
                items = items.filter(
                    ResearchProtocol.research_study_id == research_study_id)
            return items

        items = fetch_for_org(self.id)
        if items.count() or not consider_parents:
            return items
        org_id = self.partOf_id
        while org_id:
            items = fetch_for_org(org_id)
            if items.count():
                return items
            org_id = Organization.query.get(org_id).partOf_id

        # no match found; return valid (empty) query for client iteration
        return items

    def research_protocol(self, research_study_id, as_of_date):
        """Lookup research protocol for this org valid at as_of_date

        Complicated scenario as it may only be defined on the parent or
        further up the tree.  Secondly, we keep history of research protocols
        in case backdated entry is necessary.

        :return: research protocol for org (or parent org) valid as_of_date

        """

        def rp_from_org(org):
            best_candidate = None
            for rp, retired_as_of in org.rps_w_retired(research_study_id):
                if not retired_as_of:
                    best_candidate = rp
                elif retired_as_of > as_of_date:
                    best_candidate = rp
            return best_candidate

        rp = rp_from_org(self)
        if rp:
            return rp
        org = self
        while org.partOf_id:
            org = Organization.query.get(org.partOf_id)
            rp = rp_from_org(org)
            if rp:
                return rp

    def invalidation_hook(self):
        """Endpoint called during site persistence import on change

        Any site persistence aware class may implement ``invalidation_hook``
        to be notified of changes during import.

        Designed to allow for cache invalidation or other flushing needed
        on state changes.  As organizations define users affiliation with
        questionnaires via research protocol, such a change means flush
        any existing qb_timeline rows for member users

        """
        from .user import UserRoles
        from .qb_timeline import QBT

        # no easy way to determine what changed - don't take a chance
        # on leaving behind invalid cache data - purge any qb_timeline
        # rows that may be affected.
        org_ids = OrgTree().here_and_below_id(self.id)
        patient_role = Role.query.filter(
            Role.name == ROLE.PATIENT.value).one()
        patient_ids = UserOrganization.query.join(
            UserRoles, UserOrganization.user_id == UserRoles.user_id).filter(
            UserRoles.role_id == patient_role.id).filter(
            UserOrganization.organization_id.in_(org_ids)).with_entities(
            UserOrganization.user_id)
        QBT.query.filter(QBT.user_id.in_(patient_ids)).delete(
            synchronize_session=False)

    @classmethod
    def from_fhir(cls, data):
        org = cls()
        return org.update_from_fhir(data)

    def update_from_fhir(self, data):
        if 'id' in data:
            self.id = data['id']
        self.name = data.get('name')
        if 'telecom' in data:
            telecom = Telecom.from_fhir(data['telecom'])
            self.email = telecom.email
            telecom_cps = telecom.cp_dict()
            self.phone = (
                telecom_cps.get(('phone', 'work'))
                or telecom_cps.get(('phone', None)))
        if 'address' in data:
            if not data.get('address'):
                for addr in self.addresses:
                    self.addresses.remove(addr)
            for addr in data['address']:
                self.addresses.append(address.Address.from_fhir(addr))
        self.type = (
            CodeableConcept.from_fhir(data['type']) if data.get('type')
            else None)
        self.partOf_id = (
            Reference.parse(data['partOf']).id if data.get('partOf')
            else None)
        for attr in (
            'use_specific_codings',
            'race_codings',
            'ethnicity_codings',
            'indigenous_codings',
        ):
            if attr in data:
                setattr(self, attr, data.get(attr))

        by_extension_url = {
            ext['url']: ext for ext in data.get('extension', [])}
        for kls in org_extension_classes:
            args = by_extension_url.get(
                kls.extension_url, {'url': kls.extension_url})
            instance = org_extension_map(self, args)
            instance.apply_fhir()

        if 'identifier' in data:
            # track current identifiers - must remove any not requested
            remove_if_not_requested = [i for i in self.identifiers]
            for id in data['identifier']:
                identifier = Identifier.from_fhir(id).add_if_not_found()
                if identifier not in self.identifiers.all():
                    self.identifiers.append(identifier)
                else:
                    remove_if_not_requested.remove(identifier)
            for obsolete in remove_if_not_requested:
                self.identifiers.remove(obsolete)
        self.default_locale = data.get('language')
        return self

    def as_fhir(self, include_empties=True, include_inherited=False):
        """Return JSON representation of organization

        :param include_empties: if True, returns entire object definition;
            if False, empty elements are removed from the result
        :param include_inherited: if True, attributes not defined at instance
            level will be looked up climbing the org tree - first found
            defines.  by default (False) only attributes set directly on
            the (self) organization are included.  Only implemented on
            the following attributes {timezone, research_protocol}
        :return: JSON representation of a FHIR Organization resource

        """
        # TODO implement `include_inherited` on additional attributes
        d = {}
        d['resourceType'] = 'Organization'
        d['id'] = self.id
        d['name'] = self.name
        telecom = Telecom(email=self.email, contact_points=[self._phone])
        d['telecom'] = telecom.as_fhir()
        d['address'] = []
        for addr in self.addresses:
            d['address'].append(addr.as_fhir())
        d['type'] = self.type.as_fhir() if self.type else None
        d['partOf'] = (
            Reference.organization(self.partOf_id).as_fhir() if
            self.partOf_id else None)
        for attr in ('use_specific_codings', 'race_codings',
                     'ethnicity_codings', 'indigenous_codings'):
            if getattr(self, attr):
                d[attr] = True
            else:
                d[attr] = False
        extensions = []
        for kls in org_extension_classes:
            instance = org_extension_map(self, {'url': kls.extension_url})
            data = instance.as_fhir(
                include_empties=include_empties,
                include_inherited=include_inherited)
            if data:
                extensions.append(data)
        d['extension'] = extensions
        d['identifier'] = []
        for id in self.identifiers:
            d['identifier'].append(id.as_fhir())
        d['language'] = self.default_locale
        if not include_empties:
            return strip_empties(d)
        return d

    @classmethod
    def generate_bundle(cls, limit_to_ids=None, include_empties=True):
        """Generate a FHIR bundle of existing orgs ordered by ID

        :param limit_to_ids: if defined, only return the matching set,
          otherwise all organizations found
        :param include_empties: set to include empty attributes
        :return:

        """
        query = Organization.query.order_by(Organization.id)
        if limit_to_ids:
            query = query.filter(Organization.id.in_(limit_to_ids))

        orgs = [o.as_fhir(include_empties=include_empties) for o in query]

        search_link = {
            'rel': 'self',
            'href': url_for(
                'org_api.organization_search', _external=True)}
        return bundle_results(elements=orgs, links=[search_link])

    @staticmethod
    def consent_agreements(locale_code):
        """Return consent agreements for all top level organizations

        :param locale_code: preferred locale, typically user's.

        :return: dictionary keyed by top level organization id containing
          a VersionedResource for each organization IFF the organization
          has a custom consent agreement on file.  The `organization_name`
          is also added to the versioned resource to simplify UI code.

        """
        from ..views.portal import stock_consent  # local avoids cycle
        agreements = {}
        for org_id in OrgTree().all_top_level_ids():
            org = Organization.query.get(org_id)
            if not org:
                raise RuntimeError(
                    "org_id in OrgTree but not database?!"
                    " Missing: OrgTree().invalidate_cache()")

            # Not all organizations maintain consent agreements
            # include only those with such defined
            try:
                url = app_text(ConsentByOrg_ATMA.name_key(organization=org))
                resource = VersionedResource(url, locale_code=locale_code)
            except UndefinedAppText:
                # no consent found for this organization, provide
                # the dummy template
                url = url_for('portal.stock_consent', org_name=org.name,
                              _external=True)
                asset = stock_consent(org_name=org.shortname)
                resource = UnversionedResource(url=url, asset=asset)

            resource.organization_name = org.name
            resource.organization_shortname = org.shortname
            agreements[org.id] = resource
        return agreements


class OrganizationLocale(db.Model):
    __tablename__ = 'organization_locales'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='CASCADE'), nullable=False)
    coding_id = db.Column(db.ForeignKey('codings.id'), nullable=False)

    __table_args__ = (UniqueConstraint(
        'organization_id', 'coding_id', name='_organization_locale_coding'),)


class LocaleExtension(CCExtension):
    def __init__(self, organization, extension):
        self.organization, self.extension = organization, extension

    extension_url = "http://hl7.org/fhir/valueset/languages"

    @property
    def children(self):
        return self.organization.locales


class OrganizationResearchProtocol(db.Model):
    __tablename__ = 'organization_research_protocols'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='CASCADE'), nullable=False)
    research_protocol_id = db.Column(db.ForeignKey(
        'research_protocols.id', ondelete='CASCADE'), nullable=False)
    retired_as_of = db.Column(db.DateTime, nullable=True)

    # bidirectional attribute/collection of
    # "organization"/"organization_research_protocols"
    organization = db.relationship(
        Organization, backref=backref(
            "organization_research_protocols", cascade="all, delete-orphan"))

    # reference to the "ResearchProtocol" object
    research_protocol = db.relationship("ResearchProtocol")

    __table_args__ = (UniqueConstraint(
        'organization_id', 'research_protocol_id',
        name='_organization_research_protocol'),)

    def __init__(
        self, research_protocol=None, organization=None,
        retired_as_of=None
    ):
        if research_protocol:
            assert isinstance(research_protocol, ResearchProtocol)
        if organization:
            assert isinstance(organization, Organization)
        self.organization = organization
        self.research_protocol = research_protocol
        self.retired_as_of = retired_as_of

    def __repr__(self):
        return 'OrganizationResearchProtocol({}:{})'.format(
            self.organization, self.research_protocol)


class ResearchProtocolExtension(CCExtension):
    def __init__(self, organization, extension):
        self.organization, self.extension = organization, extension

    extension_url = TRUENTH_RP_EXTENSION

    def as_fhir(self, include_empties=True, include_inherited=False):
        rps = []

        def rps_from_org(org):
            for rp, retired_as_of in org.rps_w_retired(
                    research_study_id='all'):
                d = {
                    'name': rp.name,
                    'research_study_id': rp.research_study_id}
                if retired_as_of:
                    d['retired_as_of'] = FHIR_datetime.as_fhir(retired_as_of)
                rps.append(d)
            return rps

        rps = rps_from_org(self.organization)
        if rps:
            return {'url': self.extension_url, 'research_protocols': rps}
        elif include_empties:
            return {'url': self.extension_url}
        elif include_inherited:
            # Climb the org inheritance tree till an rp is found
            org = self.organization
            while True:
                if org.partOf_id is None:
                    return
                org = Organization.query.get(org.partOf_id)
                rps = rps_from_org(org)
                if rps:
                    return {
                        'url': self.extension_url,
                        'research_protocols': rps}

    def apply_fhir(self):
        if self.extension['url'] != self.extension_url:
            raise ValueError('invalid url for ResearchProtocolExtension')

        remove_if_not_requested = [
            rp for rp in self.organization.research_protocols]
        rps = self.extension.get('research_protocols', [])
        for rp in rps:
            name = rp.get('name')
            if not name:
                raise BadRequest(
                    "ResearchProtocol requires well defined name")
            existing = ResearchProtocol.query.filter_by(name=name).first()
            if not existing:
                raise NotFound(
                    "ResearchProtocol with name {} not found".format(name))
            if existing not in self.organization.research_protocols:
                # Add the intermediary table type to include the
                # retired_as_of value.  Magic of association proxy, bringing
                # one to life commits, and trying to add directly will fail
                OrganizationResearchProtocol(
                    research_protocol=existing, organization=self.organization,
                    retired_as_of=FHIR_datetime.parse(
                        rp.get('retired_as_of'), none_safe=True))
            else:
                if existing not in remove_if_not_requested:
                    raise ValueError(
                        "duplicate RP names for org {}".format(
                            self.organization.name))
                remove_if_not_requested.remove(existing)

                # Unfortunately, the association proxy requires
                # we now query for the intermediary (link) table to
                # check/set the value of `retired_as_of`

                o_rp = OrganizationResearchProtocol.query.filter(
                    OrganizationResearchProtocol.organization_id ==
                    self.organization.id).filter(
                    OrganizationResearchProtocol.research_protocol_id ==
                    existing.id).one()
                o_rp.retired_as_of = FHIR_datetime.parse(
                    rp.get('retired_as_of'), none_safe=True)

        for obsolete in remove_if_not_requested:
            self.organization.research_protocols.remove(obsolete)

    @property
    def children(self):
        raise NotImplementedError


org_extension_classes = (LocaleExtension, TimezoneExtension,
                         ResearchProtocolExtension)


def org_extension_map(organization, extension):
    """Map the given extension to the Organization

    FHIR uses extensions for elements beyond base set defined.  Lookup
    an adapter to handle the given extension for the organization.

    :param organization: the org to apply to or read the extension from
    :param extension: a dictionary with at least a 'url' key defining
        the extension.

    :returns: adapter implementing apply_fhir and as_fhir methods

    :raises :py:exc:`ValueError`: if the extension isn't recognized

    """
    for kls in org_extension_classes:
        if extension['url'] == kls.extension_url:
            return kls(organization, extension)
    # still here implies an extension we don't know how to handle
    raise ValueError("unknown extension: {}".format(extension['url']))


class UserOrganization(db.Model):
    """link table for users (n) : organizations (n)"""
    __tablename__ = 'user_organizations'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='cascade'), nullable=False)
    user_id = db.Column(db.ForeignKey(
        'users.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint(
        'user_id', 'organization_id', name='_user_organization'),)

    organization = db.relationship('Organization')


class OrganizationAddress(db.Model):
    """link table for organization : n addresses"""
    __tablename__ = 'organization_addresses'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='cascade'), nullable=False)
    address_id = db.Column(db.ForeignKey(
        'addresses.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint(
        'organization_id', 'address_id', name='_organization_address'),)


class OrganizationIdentifier(db.Model):
    """link table for organization : n identifiers"""
    __tablename__ = 'organization_identifiers'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.ForeignKey(
        'organizations.id', ondelete='cascade'), nullable=False)
    identifier_id = db.Column(db.ForeignKey(
        'identifiers.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint(
        'organization_id', 'identifier_id', name='_organization_identifier'),)
    identifier = db.relationship(
        'Identifier', cascade="save-update", foreign_keys=[identifier_id])


class OrgNode(object):
    """Node in tree of organizations - used by org tree

    Simple tree implementation to house organizations in a hierarchical
    structure.  One root - any number of nodes at each tier.  The organization
    identifiers (integers referring to the database primary key) are used
    as reference keys.

    """

    def __init__(self, id, parent=None, children=None):
        self.id = id  # root node alone has id = None
        self.parent = parent
        self.children = children if children else {}
        if self.id is None:
            assert self.parent is None

    def insert(self, id, partOf_id=None):
        """Insert new nodes into the org tree

        Designed for this special organization purpose, we expect the
        tree is built from the top (root) down, so no rebalancing is
        necessary.

        :param id: of organization to insert
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
            assert (self.id is None and partOf_id is None)
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
    an organization fits in this hierarchy.  For example, needing to lookup
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
            self.__reset_cache()

    def __reset_cache(self):
        # Internal method to manage cached org data
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
                Organization.partOf_id == partOf_id)
            ):
                new_node = node.insert(id=org.id, partOf_id=partOf_id)
                if org.id in self.lookup_table:
                    raise ValueError(
                        "Found cycle in org graph - can't add {} to table: {}"
                        "".format(org.id, self.lookup_table.keys()))
                self.lookup_table[org.id] = new_node
                if Organization.query.filter(
                    Organization.partOf_id == new_node.id
                ).count():
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
        if organization_id == 0:
            raise ValueError(
                "'none of the above' not found as it doesn't belong "
                "in OrgTree")

        if organization_id not in self.lookup_table:
            # Strange race condition - if this org id is found, reload
            # the lookup_table
            if Organization.query.get(organization_id):
                current_app.logger.warning(
                    "existing org not found in OrgTree. "
                    "lookup_table size {}".format(len(self.lookup_table)))
                self.__reset_cache()
            else:
                raise ValueError(
                    "{} not found in OrgTree".format(organization_id))
        return self.lookup_table[organization_id]

    def all_top_level_ids(self):
        """Return list of all top level organization identifiers"""
        return self.root.children.keys()

    def top_level_names(self):
        """Fetch org names for `all_top_level_ids`

        :returns: list of top level org names

        """
        results = Organization.query.filter(
            Organization.id.in_(self.all_top_level_ids())).with_entities(
            Organization.name).all()
        return [r[0] for r in results]

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
        try:
            arb = self.find(organization_id)
        except ValueError:
            return []

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
        # work through list - short circuit out if a qualified node is found
        for other_organization_id in other_organizations:
            if organization_id == other_organization_id:
                return True
            children = self.here_and_below_id(organization_id)
            if other_organization_id in children:
                return True

    def at_and_above_ids(self, organization_id):
        """Returns list of ids from any point in tree and up the parent stack

        :param organization_id: node in tree, will be included in return list
        :return: list of organization ids from the one given on up including
            every parent found in chain

        """
        ids = []
        node = self.find(organization_id)
        while node is not self.root:
            ids.append(node.id)
            node = node.parent
        return ids

    def find_top_level_orgs(self, organizations, first=False):
        """Returns top level organization(s) from those provided

        :param organizations: organizations against which top level
         organization(s) will be queried
        :param first: if set, return the first org in the result list
         rather than a set of orgs.

        :return: set of top level organization(s), or a single org if
         ``first`` is set.

        """
        results = set()
        for org in (o for o in organizations if o.id):
            top_org_id = self.find(org.id).top_level()
            results.add(Organization.query.get(top_org_id))

        if first:
            return next(iter(results)) if results else None
        return results


def org_restriction_by_role(user, requested_orgs):
    """Return list of organizations user can and wants to see

    :param requested_orgs: List of organization IDs the user has selected
        for inclusion in filtering, may be None.  If defined, the return
        list will be the intersection of the requested_orgs and the list of
        organizations the user's role gives them the right to view.

    :returns: None if no org restrictions apply, or a list of org_ids

    """
    if user.has_role(ROLE.ADMIN.value, ROLE.INTERVENTION_STAFF.value):
        # admins and intervention_staff aren't generally restricted by
        # organization - only apply a restriction if they've set a filter
        return requested_orgs

    org_list = set()
    if user.has_role(
            ROLE.CLINICIAN.value, ROLE.STAFF.value, ROLE.STAFF_ADMIN.value):
        # Build list of all organization ids, and their descendants, the
        # user belongs to
        ot = OrgTree()

        if requested_orgs:
            # for preferred filtered orgs
            requested_orgs = set(requested_orgs)
            for orgId in requested_orgs:
                if orgId == 0:  # None of the above doesn't count
                    continue
                for org in user.organizations:
                    if orgId in ot.here_and_below_id(org.id):
                        org_list.add(orgId)
                        break
        else:
            for org in user.organizations:
                if org.id == 0:  # None of the above doesn't count
                    continue
                org_list.update(ot.here_and_below_id(org.id))
        return list(org_list)


def add_static_organization():
    """Insert special `none of the above` org at index 0"""
    existing = Organization.query.get(0)
    if not existing:
        db.session.add(Organization(id=0, name='none of the above'))
