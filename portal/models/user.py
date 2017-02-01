"""User model """
from abc import ABCMeta, abstractproperty
from datetime import datetime
from dateutil import parser
from flask import abort
from flask_user import UserMixin, _call_or_get
import pytz
from sqlalchemy import text
from sqlalchemy.orm import synonym
from sqlalchemy import and_, or_, UniqueConstraint
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import ENUM
from flask_login import current_user as flask_login_current_user
from fuzzywuzzy import fuzz

from .audit import Audit


from ..extensions import db
from .fhir import as_fhir, FHIR_datetime, Observation, UserObservation
from .fhir import Coding, CodeableConcept, ValueQuantity
from .intervention import UserIntervention
from .performer import Performer
from .organization import Organization, OrgTree
import reference
from .relationship import Relationship, RELATIONSHIP
from .role import Role, ROLE
from ..system_uri import TRUENTH_IDENTITY_SYSTEM
from ..system_uri import TRUENTH_EXTENSTION_NHHD_291036
from .telecom import Telecom

INVITE_PREFIX = "__invite__"

#https://www.hl7.org/fhir/valueset-administrative-gender.html
gender_types = ENUM('male', 'female', 'other', 'unknown', name='genders',
                    create_type=False)

class Extension:
    """Abstract base class for common user extension FHIR objects"""
    __metaclass__ = ABCMeta

    def __init__(self, user, extension):
        self.user, self.extension = user, extension

    @abstractproperty
    def children(self):  # pragma: no cover
        pass

    def as_fhir(self):
        if self.children.count():
            return {'url': self.extension_url,
                    'valueCodeableConcept': {
                        'coding': [c.as_fhir() for c in self.children]}
                   }

    def apply_fhir(self):
        assert self.extension['url'] == self.extension_url
        # track current concepts - must remove any not requested
        remove_if_not_requested = {e.code: e for e in self.children}

        for coding in self.extension['valueCodeableConcept']['coding']:
            try:
                concept = Coding.query.filter_by(
                    system=coding['system'], code=coding['code']).one()
            except NoResultFound:
                raise ValueError("Unknown code: {} for system{}".format(
                                     coding['code'], coding['system']))
            if concept.code in remove_if_not_requested:
                # The concept existed before and is to be retained
                remove_if_not_requested.pop(concept.code)
            else:
                # Otherwise, it's new; add it
                self.children.append(concept)

        # Remove the stale concepts that weren't requested again
        for concept in remove_if_not_requested.values():
            self.children.remove(concept)


class UserIndigenousStatusExtension(Extension):
    # Used in place of us-core-race and us-core-ethnicity for
    # Australian configurations.
    extension_url = TRUENTH_EXTENSTION_NHHD_291036

    @property
    def children(self):
        return self.user.indigenous


class UserEthnicityExtension(Extension):
    extension_url =\
       "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity"

    @property
    def children(self):
        return self.user.ethnicities


class UserRaceExtension(Extension):
    extension_url =\
       "http://hl7.org/fhir/StructureDefinition/us-core-race"

    @property
    def children(self):
        return self.user.races


class UserTimezone(Extension):
    extension_url =\
       "http://hl7.org/fhir/StructureDefinition/user-timezone"

    def as_fhir(self):
        timezone = self.user.timezone
        if not timezone or timezone == 'None':
            timezone = 'UTC'
        return {'url': self.extension_url,
                'timezone': timezone}

    def apply_fhir(self):
        assert self.extension['url'] == self.extension_url
        if not 'timezone' in self.extension:
            abort(400, "Extension missing 'timezone' field")
        timezone = self.extension['timezone']

        # Confirm it's a recognized timezone
        try:
            pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            abort(400, "Unknown Timezone: '{}'".format(timezone))
        self.user.timezone = timezone

    @property
    def children(self):
        raise NotImplementedError


def permanently_delete_user(username, user_id=None, acting_user=None):
    """Given a username (email), purge the user from the system

    Includes wiping out audit rows, observations, etc.
    May pass either username or user_id.  Will prompt for acting_user if not
    provided.

    :param username: username (email) for user to purge
    :param user_id: id of user in liew of username
    :param acting_user: user taking the action, for record keeping

    """
    from .auth import AuthProvider
    from .tou import ToU
    from .user_consent import UserConsent

    if not acting_user:
        actor = raw_input(
            "\n\nWARNING!!!\n\n"
            " This will permanently destroy user: {}\n"
            " and all their related data.\n\n"
            " If you want to contiue, enter a valid user\n"
            " email as the acting party for our records: ".\
            format(username))
        acting_user = User.query.filter_by(username=actor).first()
    if not acting_user:
        raise ValueError("Acting user not found -- can't continue")
    if not username:
        if not user_id:
            raise ValueError("Must provide username or user_id")
        else:
            user = User.query.get(user_id)
    else:
        user = User.query.filter_by(username=username).first()
        if user_id and user.id != user_id:
                raise ValueError(
                    "Contridicting username and user_id values given")

    def purge_user(user, acting_user):
        if not user:
            raise ValueError("No such user: {}".format(username))
        if acting_user.id == user.id:
            raise ValueError(
                "Actor must be a current user other than the target")

        comment = "purged all trace of {}".format(user)  # while format works

        # purge all the types with user foreign keys, then the user itself
        UserRelationship.query.filter(
            or_(UserRelationship.user_id==user.id,
                UserRelationship.other_user_id==user.id)).delete()
        UserObservation.query.filter_by(user_id=user.id).delete()
        UserIntervention.query.filter_by(user_id=user.id).delete()
        consent_audits = Audit.query.join(
            UserConsent, UserConsent.audit_id==Audit.id).filter(
            UserConsent.user_id==user.id)
        UserConsent.query.filter_by(user_id=user.id).delete()
        for ca in consent_audits:
            db.session.delete(ca)
        tous = ToU.query.join(Audit).filter(Audit.user_id==user.id)
        for t in tous:
            db.session.delete(t)
        for o in user.observations:
            db.session.delete(o)
        # Can't delete audit rows owned by this user, in cases like observations
        # Update those to point to user doing the purge.
        ob_audits = Audit.query.join(
            Observation).filter(Audit.id==Observation.audit_id).filter(
                Audit.user_id==user.id)
        for au in ob_audits:
            au.user_id = acting_user.id
        Audit.query.filter_by(user_id=user.id).delete()
        for ap in AuthProvider.query.filter(AuthProvider.user_id==user.id):
            db.session.delete(ap)

        # the rest should die on cascade rules
        db.session.delete(user)
        db.session.commit()

        # record this event
        db.session.add(Audit(user_id=acting_user.id, comment=comment))
        db.session.commit()

    purge_user(user, acting_user)

user_extension_classes = (UserEthnicityExtension, UserRaceExtension,
                          UserTimezone, UserIndigenousStatusExtension)

def user_extension_map(user, extension):
    """Map the given extension to the User

    FHIR uses extensions for elements beyond base set defined.  Lookup
    an adapter to handle the given extension for the user.

    :param user: the user to apply to or read the extension from
    :param extension: a dictionary with at least a 'url' key defining
        the extension.  Should include a 'valueCodeableConcept' structure
        when being used in an apply context (i.e. direct FHIR data)

    :returns: adapter implementing apply_fhir and as_fhir methods

    :raises :py:exc:`exceptions.ValueError`: if the extension isn't recognized

    """
    for kls in user_extension_classes:
        if extension['url'] == kls.extension_url:
            return kls(user, extension)
    # still here implies an extension we don't know how to handle
    raise ValueError("unknown extension: {}".format(extension.url))


class User(db.Model, UserMixin):
    ## PLEASE maintain merge_with() as user model changes ##
    __tablename__ = 'users'  # Override default 'user'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    registered = db.Column(db.DateTime, default=datetime.utcnow)
    _email = db.Column('email', db.String(120), unique=True)
    phone = db.Column(db.String(40))
    gender = db.Column('gender', gender_types)
    birthdate = db.Column(db.Date)
    image_url = db.Column(db.Text)
    active = db.Column('is_active', db.Boolean(), nullable=False,
            server_default='1')
    locale_id = db.Column(db.ForeignKey('codeable_concepts.id'))
    timezone = db.Column(db.String(20), default='UTC')
    deleted_id = db.Column(
        db.ForeignKey('audit.id', use_alter=True,
                      name='user_deleted_audit_id_fk'), nullable=True)
    deceased_id = db.Column(
        db.ForeignKey('audit.id', use_alter=True,
                      name='user_deceased_audit_id_fk'), nullable=True)

    # We use email like many traditional systems use username.
    # Create a synonym to simplify integration with other libraries (i.e.
    # flask-user).  Effectively makes the attribute email avail as username
    username = synonym('email')

    # Only used for local accounts
    password = db.Column(db.String(255))
    reset_password_token = db.Column(db.String(100))
    confirmed_at = db.Column(db.DateTime())

    auth_providers = db.relationship('AuthProvider', lazy='dynamic')
    _consents = db.relationship('UserConsent', lazy='dynamic')
    indigenous = db.relationship(Coding, lazy='dynamic',
            secondary="user_indigenous")
    ethnicities = db.relationship(Coding, lazy='dynamic',
            secondary="user_ethnicities")
    groups = db.relationship('Group', secondary='user_groups',
            backref=db.backref('users', lazy='dynamic'))
    questionnaire_responses = db.relationship('QuestionnaireResponse',
            lazy='dynamic')
    races = db.relationship(Coding, lazy='dynamic',
            secondary="user_races")
    observations = db.relationship('Observation', lazy='dynamic',
            secondary="user_observations", backref=db.backref('users'))
    organizations = db.relationship('Organization', lazy='dynamic',
            secondary="user_organizations", backref=db.backref('users'))
    procedures = db.relationship('Procedure', lazy='dynamic',
            backref=db.backref('user'))
    roles = db.relationship('Role', secondary='user_roles',
            backref=db.backref('users', lazy='dynamic'))
    _locale = db.relationship(CodeableConcept, cascade="save-update")
    deleted = db.relationship('Audit', cascade="save-update",
                              foreign_keys=[deleted_id])
    deceased = db.relationship('Audit', cascade="save-update",
                              foreign_keys=[deceased_id])
    documents = db.relationship('UserDocument', lazy='dynamic')

    ###
    ## PLEASE maintain merge_with() as user model changes ##
    ###

    assessment_status = 'undetermined'

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "user {0.id}".format(self)

    def __setattr__(self, name, value):
        """Make sure deleted users aren't being updated"""
        if not name.startswith('_'):
            if getattr(self, 'deleted'):
                raise ValueError("can not update {} on deleted {}".format(
                    name, self))
        return super(User, self).__setattr__(name, value)

    @property
    def all_consents(self):
        """Access to all consents including deleted and expired"""
        return self._consents

    @property
    def valid_consents(self):
        """Access to consents that have neither been deleted or expired"""
        now = datetime.utcnow()
        return self._consents.filter(
            text("expires>:now and deleted_id is null")).params(now=now)

    @property
    def display_name(self):
        if self.first_name and self.last_name:
            return ' '.join((self.first_name, self.last_name))
        else:
            return self.username

    @property
    def locale(self):
        if self._locale and self._locale.codings and (len(self._locale.codings) > 0):
            return self._locale.codings[0]
        return None

    @property
    def locale_code(self):
        if self.locale:
            return self.locale.code
        return None

    @property
    def locale_name(self):
        if self.locale:
            return self.locale.display
        return None

    @locale.setter
    def locale(self, lang_info):
        # lang_info is a tuple of format (language_code,language_name)
        # IETF BCP 47 standard uses hyphens, bust we instead store w/ underscores,
        # to better integrate with babel/LR URLs/etc
        data = {"coding": [{'code': lang_info[0], 'display': lang_info[1],
                  'system': "urn:ietf:bcp:47"}]}
        self._locale = CodeableConcept.from_fhir(data)

    @hybrid_property
    def email(self):
        # Called in different contexts - only compare string
        # value if it's a base string type, as opposed to when
        # its being used in a query statement (email.ilike('foo'))
        if isinstance(self._email, basestring):
            if self._email.startswith(INVITE_PREFIX):
                return self._email[len(INVITE_PREFIX):]

        return self._email

    @email.setter
    def email(self, email):
        self._email = email

    def mask_email(self, prefix=INVITE_PREFIX):
        """Mask temporary account email to avoid collision with registered

        Temporary user accounts created for the purpose of invites get
        in the way of the user creating a registered account.  Add a hidden
        prefix to the email address in the temporary account to avoid
        collision.

        """
        if not self._email.startswith(prefix):
            self._email = prefix + self._email

    def add_organization(self, organization_name):
        """Shortcut to add a clinic/organization by name"""
        org = Organization.query.filter_by(name=organization_name).one()
        if org not in self.organizations:
            self.organizations.append(org)

    def leaf_organizations(self):
        """Return list of 'leaf' organization ids for user's orgs

        Users, especially staff, have arbitrary number of organization
        associations, at any level of the organization hierarchy.  This
        method looks up all child leaf nodes from the users existing orgs.

        """
        leaves = set()
        OT = OrgTree()
        for org in self.organizations:
            leaves.update(OT.all_leaves_below_id(org.id))
        return list(leaves)

    def add_observation(self, fhir, audit):
        if not 'coding' in fhir['code']:
            return 400, "requires at least one CodeableConcept"
        if not 'valueQuantity' in fhir:
            return 400, "missing required 'valueQuantity'"

        cc = CodeableConcept.from_fhir(fhir['code']).add_if_not_found()

        v = fhir['valueQuantity']
        vq = ValueQuantity(value=v.get('value'),
                units=v.get('units'),
                system=v.get('system'),
                code=v.get('code')).add_if_not_found(True)

        issued = fhir.get('issued') and\
                parser.parse(fhir.get('issued')) or None
        observation = Observation(
            audit=audit,
            status=fhir.get('status'),
            issued=issued,
            codeable_concept_id=cc.id,
            value_quantity_id=vq.id).add_if_not_found(True)
        if 'performer' in fhir:
            for p in fhir['performer']:
                performer = Performer.from_fhir(p)
                observation.performers.append(performer)
        UserObservation(user_id=self.id,
                        observation_id=observation.id).add_if_not_found()
        return 200, "added {} to user {}".format(observation, self.id)

    def add_relationship(self, other_user, relationship_name):
        # confirm it's not already defined
        relationship = Relationship.query.filter_by(
                name=relationship_name).first()
        existing = UserRelationship.query.filter_by(user_id=self.id,
                other_user_id=other_user.id,
                relationship_id=relationship.id).first()
        if existing:
            raise ValueError("requested relationship already defined")

        new_relationship = UserRelationship(user_id=self.id,
                other_user_id=other_user.id,
                relationship_id=relationship.id)
        self.relationships.append(new_relationship)

    def has_relationship(self, relationship_name, other_user):
        relationship = Relationship.query.filter_by(
                name=relationship_name).first()
        for r in self.relationships:
            if (r.relationship_id == relationship.id and
                r.other_user_id == other_user.id):
                return True
        return False

    def add_service_account(self):
        """Service account generation.

        For automated, authenticated access to protected API endpoints,
        a service user can be created and used to generate a long-life
        bearer token.  The account is a user with the service role,
        attached to a sposor account - the (self) individual creating it.

        Only a single service account is allowed per user.  If one is
        found to exist for this user, simply return it.

        """
        for rel in self.relationships:
            if rel.relationship.name == RELATIONSHIP.SPONSOR:
                return User.query.get(rel.other_user_id)

        service_user = User(username=(u'service account sponsored by {}'.
                              format(self.username)))
        db.session.add(service_user)
        add_role(service_user, ROLE.SERVICE)
        self.add_relationship(service_user, RELATIONSHIP.SPONSOR)
        return service_user

    def fetch_values_for_concept(self, codeable_concept):
        """Return any matching ValueQuantities for this user"""
        # User may not have persisted concept - do so now for match
        codeable_concept = codeable_concept.add_if_not_found()

        return [obs.value_quantity for obs in self.observations if\
                obs.codeable_concept_id == codeable_concept.id]

    def save_constrained_observation(self, codeable_concept, value_quantity,
                                    audit):
        """Add or update the value for given concept as observation

        We can store any number of observations for a patient, and
        for a given concept, any number of values.  BUT sometimes we
        just want to update the value and retain a single observation
        for the concept.  Use this method is such a case, i.e. for
        a user's 'biopsy' status.

        """
        # User may not have persisted concept or value - CYA
        codeable_concept = codeable_concept.add_if_not_found()
        value_quantity = value_quantity.add_if_not_found()

        existing = [obs for obs in self.observations if\
                    obs.codeable_concept_id == codeable_concept.id]
        assert len(existing) < 2  # it's a constrained concept afterall

        if existing:
            if existing[0].value_quantity_id == value_quantity.id:
                # perfect match -- update audit info
                existing[0].audit = audit
                return
            else:
                # We don't want multiple observations for this concept
                # with different values.  Delete old and add new
                self.observations.remove(existing[0])

        observation = Observation(codeable_concept_id=codeable_concept.id,
                                  value_quantity_id=value_quantity.id,
                                  audit=audit)
        self.observations.append(observation.add_if_not_found())

    def clinical_history(self, requestURL=None):
        now = datetime.utcnow()
        fhir = {"resourceType": "Bundle",
                "title": "Clinical History",
                "link": [{"rel": "self", "href": requestURL},],
                "updated": as_fhir(now),
                "entry": []}

        for ob in self.observations:
            fhir['entry'].append({"title": "Patient Observation",
                    "updated": as_fhir(now),
                    "author": [{"name": "Truenth Portal"},],
                    "content": ob.as_fhir()})
        return fhir

    def procedure_history(self, requestURL=None):
        now = datetime.utcnow()
        fhir = {"resourceType": "Bundle",
                "title": "Procedure History",
                "link": [{"rel": "self", "href": requestURL},],
                "updated": as_fhir(now),
                "entry": []}

        for proc in self.procedures:
            fhir['entry'].append({"resource": proc.as_fhir()})
        return fhir

    def as_fhir(self):
        def identifiers():
            """build and return list of idetifiers"""
            ids = []
            ids.append(
                {'use': 'official',
                 'system': '{system}/{provider}'.format(
                     system=TRUENTH_IDENTITY_SYSTEM,
                     provider='TrueNTH-identity'),
                 'assigner': {'display': 'TrueNTH'},
                 'value': self.id})
            ids.append(
                {'use': 'secondary',
                 'system': '{system}/{provider}'.format(
                     system=TRUENTH_IDENTITY_SYSTEM,
                     provider='TrueNTH-username'),
                 'assigner': {'display': 'TrueNTH'},
                 'value': self.username})
            for provider in self.auth_providers:
                ids.append(provider.as_fhir())
            return ids

        def careProviders():
            """build and return list of careProviders (AKA clinics)"""
            orgs = []
            for o in self.organizations:
                orgs.append(reference.Reference.organization(o.id).as_fhir())
            return orgs

        def deceased():
            """FHIR spec suggests ONE of deceasedBoolean or deceasedDateTime"""
            if not self.deceased_id:
                return {"deceasedBoolean": False}

            # We maintain an audit row from when the user was marked
            # as deceased.  If "time of death" is in the content, the
            # audit timestamp is good - otherwise, return the boolean
            audit = self.deceased
            if "time of death" in audit.comment:
                return {"deceasedDateTime":
                        FHIR_datetime.as_fhir(audit.timestamp)}
            return {"deceasedBoolean": True}

        d = {}
        d['resourceType'] = "Patient"
        d['identifier'] = identifiers()
        d['name'] = {}
        if self.first_name:
            d['name']['given'] = self.first_name
        if self.last_name:
            d['name']['family'] = self.last_name
        if self.birthdate:
            d['birthDate'] = as_fhir(self.birthdate)
        d.update(deceased())
        if self.gender:
            d['gender'] = self.gender
        d['status'] = 'registered' if self.registered else 'unknown'
        if self._locale:
            d['communication'] = [{"language": self._locale.as_fhir()}]
        telecom = Telecom(email=self.email, phone=self.phone)
        d['telecom'] = telecom.as_fhir()
        d['photo'] = []
        if self.image_url:
            d['photo'].append({'url': self.image_url})
        extensions = []
        for kls in user_extension_classes:
            instance = user_extension_map(self, {'url': kls.extension_url})
            data = instance.as_fhir()
            if data:
                extensions.append(data)
        if extensions:
            d['extension'] = extensions
        d['careProvider'] = careProviders()
        if self.deleted_id:
            d['deleted'] = FHIR_datetime.as_fhir(self.deleted.timestamp)
        return d

    def update_consents(self, consent_list, acting_user):
        """Update user's consents

        Adds the provided list of consent agreements to the user.
        If the user had pre-existing consent agreements between the
        same organization_id, the new will replace the old

        """
        delete_consents = []  # capture consents being replaced
        for consent in consent_list:
            audit = Audit(user_id=acting_user.id,
                          comment="Adding consent agreement")
            # Look for existing consent for this user/org
            for existing_consent in self.valid_consents:
                if existing_consent.organization_id == consent.organization_id:
                    delete_consents.append(existing_consent)

            if hasattr(consent, 'acceptance_date'):
                # Move data to where it belongs, in the audit row
                audit.timestamp = consent.acceptance_date
                del consent.acceptance_date

            consent.audit = audit
            db.session.add(consent)
        for replaced in delete_consents:
            replaced.deleted = Audit(
                comment="new consent replacing existing", user_id=self.id)
        db.session.commit()

    def update_orgs(self, org_list, acting_user, excuse_top_check=False):
        """Update user's organizations

        Uses given list of organizations as the definitive list for
        the user - meaning any current affiliations not mentioned will
        be deleted.

        :param org_list: list of organization objects for user's orgs
        :param acting_user: user behind the request for permission checks
        :param excuse_top_check: Set True to excuse check for changes
          to top level orgs, say during initial account creation

        """

        def allow_org_change(org, user, acting_user):
            """don't allow non-admin providers to change top level orgs

            as per
            https://www.pivotaltracker.com/n/projects/1225464/stories/133286317
            raise exception if non-admin provider is attempting to
            change their top level orgs

            """
            if org.partOf_id is None:  # top-level orgs
                if not acting_user.has_role(ROLE.ADMIN) and\
                   acting_user.has_role(ROLE.PROVIDER):
                    raise ValueError("non-admin providers can't change "
                                     "their high-level orgs")
            return True

        remove_if_not_requested = {org.id: org for org in
                                   self.organizations}
        for org in org_list:
            if org.id in remove_if_not_requested:
                remove_if_not_requested.pop(org.id)
            if org not in self.organizations:
                if not excuse_top_check:
                    allow_org_change(org, user=self, acting_user=acting_user)
                self.organizations.append(org)
        for org in remove_if_not_requested.values():
            if not excuse_top_check:
                allow_org_change(org, user=self, acting_user=acting_user)
            self.organizations.remove(org)

    def update_roles(self, role_list, acting_user):
        """Update user's roles

        :param role_list: list of role objects defining exactly what
          roles the user should have.  Any existing roles not mentioned
          will be deleted from user's list
        :param acting_user: user performing action, for permissions, etc.

        """
        # Don't allow promotion of service accounts
        if self.has_role(ROLE.SERVICE):
            abort(400, "Promotion of service users not allowed")

        remove_if_not_requested = {role.id: role for role in self.roles}
        for role in role_list:
            # Don't allow others to add service to their accounts
            if role.name == ROLE.SERVICE:
                abort(400, "Service role is restricted to service accounts")
            if role.id in remove_if_not_requested:
                remove_if_not_requested.pop(role.id)
            else:
                self.roles.append(role)
                audit = Audit(
                    comment="added {} to user {}".format(
                    role, self.id), user_id=acting_user.id)
                db.session.add(audit)

        for stale_role in remove_if_not_requested.values():
            self.roles.remove(stale_role)
            audit = Audit(
                comment="deleted {} from user {}".format(
                stale_role, self.id), user_id=acting_user.id)
            db.session.add(audit)

    def update_from_fhir(self, fhir, acting_user):
        """Update the user's demographics from the given FHIR

        If a field is defined, it is the final definition for the respective
        field, resulting in a deletion of existing values in said field
        that are not included.

        :param fhir: JSON defining portions of the user demographics to change
        :param acting_user: user requesting the change

        """
        def v_or_n(value):
            """Return None unless the value contains data"""
            if value:
                return value.rstrip() or None

        def update_deceased(fhir):
            if 'deceasedDateTime' in fhir:
                dt = FHIR_datetime.parse(fhir['deceasedDateTime'],
                                         error_subject='deceasedDataTime')
                if self.deceased_id:
                    # only update if the datetime is different
                    if dt == self.deceased.timestamp:
                        return  # short circuit out of here
                # Given a time, store and mark as "time of death"
                audit = Audit(
                    user_id=current_user().id, timestamp=dt,
                    comment="time of death for user {}".format(self.id))
                self.deceased = audit
            elif 'deceasedBoolean' in fhir:
                if fhir['deceasedBoolean'] == False:
                    if self.deceased_id:
                        # Remove deceased record from the user, but maintain
                        # the old audit row.
                        self.deceased_id = None
                        audit = Audit(
                            user_id=current_user().id,
                            comment=("Remove existing deceased from "
                                     "user {}".format(self.id)))
                        db.session.add(audit)
                else:
                    # still marked with an audit, but without the special
                    # comment syntax and using default (current) time.
                    audit = Audit(
                        user_id=current_user().id,
                        comment=("Marking user {} as "
                                 "deceased".format(self.id)))
                    self.deceased = audit

        if 'name' in fhir:
            self.first_name = v_or_n(
                fhir['name'].get('given')) or self.first_name
            self.last_name = v_or_n(
                fhir['name'].get('family')) or self.last_name
        if 'birthDate' in fhir:
            try:
                fhir['birthDate'].strip()
                self.birthdate = datetime.strptime(
                    fhir['birthDate'], '%Y-%m-%d')
            except (AttributeError, ValueError):
                abort(400, "birthDate '{}' doesn't match expected format "
                      "'%Y-%m-%d'".format(fhir['birthDate']))
        update_deceased(fhir)
        if 'gender' in fhir and fhir['gender']:
            self.gender = fhir['gender'].lower()
        if 'telecom' in fhir:
            telecom = Telecom.from_fhir(fhir['telecom'])
            self.email = telecom.email
            self.phone = telecom.phone
        if 'communication' in fhir:
            for e in fhir['communication']:
                if 'language' in e:
                    self._locale = CodeableConcept.from_fhir(e.get('language'))
        if 'extension' in fhir:
            # a number of elements live in extension - handle each in turn
            for e in fhir['extension']:
                instance = user_extension_map(self, e)
                instance.apply_fhir()
        if 'careProvider' in fhir:
            org_list = [reference.Reference.parse(item) for item in
                        fhir['careProvider']]
            self.update_orgs(org_list, acting_user)
        db.session.add(self)

    def merge_with(self, other_id):
        """merge details from other user into self

        Part of an account generation or login flow.  Scenarios include
        a provider or an intervention setting up a weakly authenticated
        account (typically the *other_id*) for the invitation process.
        Once the user logs into an existing account or registers a new (self)
        we need to pull the data set up by the provider into this user account.

        """
        other = User.query.get(other_id)
        if not other:
            abort(404, 'other_id {} not found'.format(other_id))

        # direct attributes on user
        # intentionally skip {registered, password, confirmed_at,
        # reset_password_token}
        for attr in ('email', 'first_name', 'last_name', 'birthdate',
                     'gender', 'phone', 'locale_id', 'timezone',
                     'image_url', 'active', 'deleted_id', 'deceased_id',
                    ):
            if not getattr(other, attr):
                continue
            if not getattr(self, attr):
                setattr(self, attr, getattr(other, attr))
            # value present in both.  assume user just set to best value

        # n-to-n relationships on user
        for relationship in ('organizations', '_consents', 'procedures',
                             'observations', 'relationships', 'roles',
                             'races', 'ethnicities', 'groups',
                             'questionnaire_responses'):
            self_entity = getattr(self, relationship)
            other_entity = getattr(other, relationship)
            if relationship == 'roles':
                # We don't copy over the roles used to mark the weak account
                append_list = [item for item in other_entity if item not in
                               self_entity and item.name not in
                               ('write_only',
                                'promote_without_identity_challenge')]
            else:
                append_list = [item for item in other_entity if item not in
                               self_entity]
            for item in append_list:
                self_entity.append(item)

    def check_role(self, permission, other_id):
        """check user for adequate role

        if user is an admin or a service account, grant carte blanche
        otherwise, must be self or have a relationship granting permission
        to "verb" the other user.

        returns true if permission should be granted, raises 404 if the
        other_id can't be found, otherwise raise a 401

        """
        assert(permission in ('view', 'edit'))  # limit vocab for now
        if self.id == other_id:
            return True
        try:
            int(other_id)
        except ValueError:
            abort(400, "Non Integer value for User ID: {}".format(other_id))
        other = User.query.get(other_id)
        if not other:
            abort(404, "User not found {}".format(other_id))

        if self.has_role(ROLE.ADMIN):
            return True
        if self.has_role(ROLE.SERVICE):
            # Ideally, only users attached to the same intervention
            # as the service token would qualify.  Edge cases around
            # account creation and loose coupling between patients
            # and interventions result in carte blanche for service
            return True

        if self.has_role(ROLE.PROVIDER):
            # Providers have full access to all patients with a valid consent
            # at or below the same level of the org tree as provider has
            # associations with.  Furthermore, a patient may have a consent
            # agreement at a higher level in the orgtree than the provider,
            # in which case the patient's organization must be a child
            # of the provider's organization for access.

            # As long as the consent is valid (not expired or deleted) it's
            # adequate for 'view'.  'edit' requires the staff_editable option
            # on the consent.
            orgtree = OrgTree()
            if other.has_role(ROLE.PATIENT):
                if permission == 'edit':
                    others_con_org_ids = [
                        oc.organization_id for oc in other.valid_consents
                        if oc.staff_editable]
                else:
                    others_con_org_ids = [
                        oc.organization_id for oc in other.valid_consents]
                org_ids = [org.id for org in self.organizations]
                for org_id in org_ids:
                    if orgtree.at_or_below_ids(org_id, others_con_org_ids):
                        return True
                #Still here implies time to check 'furthermore' clause
                others_orgs = [org.id for org in other.organizations]
                for consented_org in others_con_org_ids:
                    if orgtree.at_or_below_ids(consented_org, org_ids):
                        # Okay, consent is partent of staff org
                        # but it's only good if the patient's *org*
                        # is at or below the staff's org (could be sibling
                        # or down different branch of tree)
                        for org_id in org_ids:
                            if orgtree.at_or_below_ids(org_id, others_orgs):
                                return True

        abort(401, "Inadequate role for %s of %d" % (permission, other_id))

    def has_role(self, role_name):
        return role_name in [r.name for r in self.roles]

    def provider_html(self):
        """Helper used from templates to display any custom provider text

        Interventions can add personalized HTML for care providers
        to consume on the /patients list.  Look up any values for this user
        on all interventions.

        """
        uis = UserIntervention.query.filter(and_(
            UserIntervention.user_id == self.id,
            UserIntervention.provider_html != None))
        if uis.count() == 0:
            return ""
        if uis.count() == 1:
            return uis[0].provider_html
        else:
            return '<div>' + '</div><div>'.join(
                [ui.provider_html for ui in uis]) + '</div>'

    def fuzzy_match(self, first_name, last_name, birthdate):
        """Returns probability score [0-100] of it being the same user"""
        # remove case issues as it confuses the match
        scores = []
        fname = self.first_name or ''
        lname = self.last_name or ''
        scores.append(fuzz.ratio(fname.lower(), first_name.lower()))
        scores.append(fuzz.ratio(lname.lower(), last_name.lower()))

        # birthdate is trickier - raw delta doesn't make sense.  treat
        # it like a string, mismatch always results in a 0 score
        dob = self.birthdate or datetime.utcnow()
        if (dob.strftime('%d%m%Y') != birthdate.strftime('%d%m%Y')):
            return 0
        return sum(scores) / len(scores)


    def delete_user(self, acting_user):
        """Mark user deleted from the system

        Due to audit constraints, we do NOT actually delete the user, but
        mark the user as deleted.  See `permanently_delete_user` for
        more serious alternative.

        :param self: user to mark deleted
        :param acting_user: individual executing the command, for audit trail

        """
        from .audit import Audit
        from .auth import Client, Token

        if self == acting_user:
            raise ValueError("can't delete self")
        if self is None or acting_user is None:
            raise ValueError("both user and acting_user must be well defined")

        # Don't allow deletion of users with client applications
        clients = Client.query.filter_by(user_id=self.id)
        if clients.count():
            raise ValueError("Users owning client applications can not "
                             "be deleted.  Delete client apps first: {}".format(
                                 [client.id for client in clients]))

        self.active = False
        self.deleted = Audit(user_id=acting_user.id,
                             comment="marking deleted {}".format(self))

        # purge any outstanding access tokens
        Token.query.filter_by(user_id=self.id).delete()
        db.session.commit()


def add_authomatic_user(authomatic_user, image_url):
    """Given the result from an external IdP, create a new user"""
    user = User(
            first_name=authomatic_user.first_name,
            last_name=authomatic_user.last_name,
            birthdate=authomatic_user.birth_date,
            gender=authomatic_user.gender,
            email=authomatic_user.email,
            image_url=image_url)
    db.session.add(user)
    return user


def add_anon_user():
    """Anonymous user generation.

    Acts like real user without any authentication.  Used to persist
    data and handle similar communication with client apps (interventions).

    Bound to the session - an anonymous user can also be promoted to
    a real user at a later time in the session.

    """
    user = User()
    db.session.add(user)
    add_role(user, ROLE.ANON)
    return user


class RoleError(ValueError):
    pass


def add_role(user, role_name):
    role = Role.query.filter_by(name=role_name).first()
    assert(role)
    # don't allow promotion of service users
    if user.has_role(ROLE.SERVICE):
        raise RoleError("service accounts can't be promoted")

    new_role = UserRoles(user_id=user.id,
            role_id=role.id)
    db.session.add(new_role)
    return user


def current_user():
    """Obtain the "current" user object

    Works for both remote oauth sessions and locally logged in sessions.

    returns current user object, or None if not logged in (local or remote)
    """
    from flask import request, session

    uid = None
    if 'id' in session:
        # Locally logged in
        uid = session['id']
    elif _call_or_get(flask_login_current_user.is_authenticated):
        uid = flask_login_current_user.id
    elif hasattr(request, 'oauth'):
        # Remote OAuth - 'id' lives in request.oauth.user.id:
        uid = request.oauth.user.id
    if uid:
        with db.session.no_autoflush:
            return User.query.get(uid)
    return None


def get_user(uid):
    if uid:
        return User.query.get(uid)


class UserRoles(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id',
        ondelete='CASCADE'), nullable=False)
    role_id = db.Column(db.Integer(), db.ForeignKey('roles.id',
        ondelete='CASCADE'), nullable=False)

    __table_args__ = (UniqueConstraint('user_id', 'role_id',
        name='_user_role'),)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "UserRole {0.user_id}:{0.role_id}".format(self)


def flag_test():  # pragma: no test
    """Find all non-service users and flag as test"""

    users = User.query.filter(
        ~User.roles.any(Role.name.in_([ROLE.TEST, ROLE.SERVICE]))
    )

    for user in users:
        add_role(user, ROLE.TEST)
    db.session.commit()

class UserRelationship(db.Model):
    """SQLAlchemy class for `user_relationships` table

    Relationship is assumed to be ordered such that:
        <user_id> has a <relationship.name> with <other_user_id>

    """
    __tablename__ = 'user_relationships'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id',
        ondelete='CASCADE'), nullable=False)
    other_user_id = db.Column(db.Integer(), db.ForeignKey('users.id',
        ondelete='CASCADE'), nullable=False)
    relationship_id = db.Column(db.Integer(),
        db.ForeignKey('relationships.id', ondelete='CASCADE'), nullable=False)

    user = db.relationship("User", backref='relationships',
                           foreign_keys=[user_id])
    other_user = db.relationship("User",
        foreign_keys=[other_user_id])
    relationship = db.relationship("Relationship",
        foreign_keys=[relationship_id])

    __table_args__ = (UniqueConstraint('user_id', 'other_user_id',
        'relationship_id', name='_user_relationship'),)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "{0.relationship} between {0.user_id} and "\
            "{0.other_user_id}".format(self)

