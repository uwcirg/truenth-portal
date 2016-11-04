"""User model """
from abc import ABCMeta, abstractproperty
from datetime import datetime, timedelta
from dateutil import parser
from flask import abort
from flask_user import UserMixin, _call_or_get
import pytz
from sqlalchemy import text
from sqlalchemy.orm import synonym
from sqlalchemy import and_, UniqueConstraint
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import ENUM
from flask_login import current_user as flask_login_current_user
from fuzzywuzzy import fuzz

from ..extensions import db
from .fhir import as_fhir, Observation, UserObservation
from .fhir import Coding, CodeableConcept, ValueQuantity
from .intervention import UserIntervention
from .performer import Performer
from .organization import Organization
import reference
from .relationship import Relationship, RELATIONSHIP
from .role import Role, ROLE
from ..system_uri import TRUENTH_IDENTITY_SYSTEM
from ..system_uri import TRUENTH_EXTENSTION_NHHD_291036
from .telecom import Telecom
import random

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


def delete_user(username):
    """Given a username (email), purge the user from the system

    Includes wiping out audit rows, observations, etc.

    """
    from .audit import Audit
    from .tou import ToU
    from .intervention import UserIntervention
    from .user_consent import UserConsent

    actor = raw_input("\n\nWARNING!!!\n\n"
                      " This will permanently destroy user: {}\n"
                      " and all their related data.\n\n"
                      " If you want to contiue, enter a valid user\n"
                      " email as the acting party for our records: ".\
                      format(username))
    acting_user = User.query.filter_by(username=actor).first()
    if not acting_user or actor == username:
        raise ValueError("Actor must be a current user other than the target")
    user = User.query.filter_by(username=username).first()
    if not user:
        raise ValueError("No such user: {}".format(username))

    # purge all the types with user foreign keys, then the user itself
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
    audits = Audit.query.filter_by(user_id=user.id).delete()

    # the rest should die on cascade rules
    db.session.delete(user)
    db.session.commit()

    # record this event
    db.session.add(Audit(
        user_id=acting_user.id,
        comment="purged all trace of user {}".format(username)))
    db.session.commit()


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
    locale = db.relationship(CodeableConcept, cascade="save-update")

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

    # FIXME kludge for random demo data
    @property
    def randomDueDate(self):
    	return datetime(random.randint(2016, 2017), random.randint(1, 12), random.randint(1, 28))
    # dueDate_timedelta = randomDueDate - date.today()


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
        if self.gender:
            d['gender'] = self.gender
        d['status'] = 'registered' if self.registered else 'unknown'
        if self.locale:
            d['communication'] = [{"language": self.locale.as_fhir()}]
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
        return d

    def update_from_fhir(self, fhir):
        """Update the user's demographics from the given FHIR

        If a field is defined, it is the final definition for the respective
        field, resulting in a deletion of existing values in said field
        that are not included.

        """
        def v_or_n(value):
            """Return None unless the value contains data"""
            return value.rstrip() or None

        if 'name' in fhir:
            self.first_name = v_or_n(fhir['name']['given']) or self.first_name
            self.last_name = v_or_n(fhir['name']['family']) or self.last_name
        if 'birthDate' in fhir and fhir['birthDate'].strip():
            self.birthdate = datetime.strptime(fhir['birthDate'],
                    '%Y-%m-%d')
        if 'gender' in fhir and fhir['gender']:
            self.gender = fhir['gender'].lower()
        if 'telecom' in fhir:
            telecom = Telecom.from_fhir(fhir['telecom'])
            self.email = telecom.email
            self.phone = telecom.phone
        if 'communication' in fhir:
            for e in fhir['communication']:
                if 'language' in e:
                    self.locale = CodeableConcept.from_fhir(e['language'])
        if 'extension' in fhir:
            # a number of elements live in extension - handle each in turn
            for e in fhir['extension']:
                instance = user_extension_map(self, e)
                instance.apply_fhir()
        if 'careProvider' in fhir:
            remove_if_not_requested = {org.id: org for org in
                                       self.organizations}
            for item in fhir['careProvider']:
                org = reference.Reference.parse(item)
                if org.id in remove_if_not_requested:
                    remove_if_not_requested.pop(org.id)
                if org not in self.organizations:
                    self.organizations.append(org)
            for org in remove_if_not_requested.values():
                self.organizations.remove(org)
        db.session.add(self)

    def merge_with(self, other_id):
        """merge details from other user into self

        Part of an account generation or login flow - scenarios include
        a provider setting up an account (typically the *other_id*) and
        then a user logs into an existing account or registers a new (self)
        and now we need to pull the data set up by the provider into the
        new account.

        """
        other = User.query.get(other_id)
        if not other:
            abort(404, 'other_id {} not found'.format(other_id))

        for attr in ('email', 'first_name', 'last_name', 'birthdate',
                     'gender', 'phone', 'locale_id', 'timezone'):
            if not getattr(other, attr):
                continue
            if not getattr(self, attr):
                setattr(self, attr, getattr(other, attr))
            # value present in both.  assume user just set to best value

        for relationship in ('organizations', '_consents', 'procedures',
                             'observations', 'relationships', 'roles',
                             'races', 'ethnicities', 'groups'):
            self_entity = getattr(self, relationship)
            other_entity = getattr(other, relationship)
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
        for role in self.roles:
            if role.name in (ROLE.ADMIN, ROLE.SERVICE):
                # Admin and service accounts have carte blanche
                return True
            if role.name == ROLE.PROVIDER:
                # Providers get carte blanche on members of the
                # same organization
                user_orgs = set(self.organizations)
                others_orgs = set(User.query.get(other_id).organizations)
                if user_orgs.intersection(others_orgs):
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
        scores.append(fuzz.ratio(self.first_name.lower(), first_name.lower()))
        scores.append(fuzz.ratio(self.last_name.lower(), last_name.lower()))

        # birthdate is trickier - raw delta doesn't make sense.  treat
        # it like a string, assuming only typos for a mismatch
        scores.append(fuzz.ratio(self.birthdate.strftime('%d%m%Y'),
                                 birthdate.strftime('%d%m%Y')))
        return sum(scores) / len(scores)


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

