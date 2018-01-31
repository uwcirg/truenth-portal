"""User model """
from cgi import escape
from datetime import datetime
from dateutil import parser
from flask import abort, current_app
from flask_user import UserMixin, _call_or_get
from sqlalchemy import text
from sqlalchemy.orm import synonym, class_mapper, ColumnProperty
from sqlalchemy import and_, or_, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import ENUM
from StringIO import StringIO
from flask_login import current_user as flask_login_current_user
from fuzzywuzzy import fuzz
import regex
import time

from .audit import Audit
from .codeable_concept import CodeableConcept
from .coding import Coding
from ..dict_tools import dict_match, strip_empties
from .encounter import Encounter
from ..database import db
from ..date_tools import as_fhir, FHIR_datetime
from .extension import CCExtension, TimezoneExtension
from .fhir import Observation, UserObservation
from .fhir import ValueQuantity
from .identifier import Identifier
from .intervention import UserIntervention
from .notification import UserNotification
from .organization import Organization, OrgTree
from .performer import Performer
from .practitioner import Practitioner
import reference
from .relationship import Relationship, RELATIONSHIP
from .role import Role, ROLE
from ..system_uri import (
    IETF_LANGUAGE_TAG,
    TRUENTH_EXTENSTION_NHHD_291036,
    TRUENTH_EXTERNAL_STUDY_SYSTEM,
    TRUENTH_ID,
    TRUENTH_PROVIDER_SYSTEMS,
    TRUENTH_USERNAME)
from .telecom import ContactPoint, Telecom

INVITE_PREFIX = "__invite__"
NO_EMAIL_PREFIX = "__no_email__"
DELETED_PREFIX = "__deleted_{time}__"
DELETED_REGEX = r"__deleted_\d+__(.*)"

# https://www.hl7.org/fhir/valueset-administrative-gender.html
gender_types = ENUM('male', 'female', 'other', 'unknown', name='genders',
                    create_type=False)

internal_identifier_systems = (
    TRUENTH_ID, TRUENTH_USERNAME) + TRUENTH_PROVIDER_SYSTEMS


class UserIndigenousStatusExtension(CCExtension):
    # Used in place of us-core-race and us-core-ethnicity for
    # Australian configurations.
    def __init__(self, user, extension):
        self.user, self.extension = user, extension

    extension_url = TRUENTH_EXTENSTION_NHHD_291036

    @property
    def children(self):
        return self.user.indigenous


class UserEthnicityExtension(CCExtension):
    def __init__(self, user, extension):
        self.user, self.extension = user, extension

    extension_url =\
        "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity"

    @property
    def children(self):
        return self.user.ethnicities


class UserRaceExtension(CCExtension):
    def __init__(self, user, extension):
        self.user, self.extension = user, extension

    extension_url =\
        "http://hl7.org/fhir/StructureDefinition/us-core-race"

    @property
    def children(self):
        return self.user.races


def permanently_delete_user(
        username,
        user_id=None,
        acting_user=None,
        actor=None):
    """Given a username (email), purge the user from the system

    Includes wiping out audit rows, observations, etc.
    May pass either username or user_id.  Will prompt for acting_user if not
    provided.

    :param username: username (email) for user to purge
    :param user_id: id of user in liew of username
    :param acting_user: user taking the action, for record keeping

    """
    from .tou import ToU

    if not acting_user:
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
            or_(UserRelationship.user_id == user.id,
                UserRelationship.other_user_id == user.id)).delete()
        tous = ToU.query.join(Audit).filter(Audit.subject_id == user.id)
        for t in tous:
            db.session.delete(t)

        # the rest should die on cascade rules
        db.session.delete(user)
        db.session.commit()

        # record this event
        db.session.add(
            Audit(user_id=acting_user.id, comment=comment,
                  subject_id=acting_user.id, context='account'))
        db.session.commit()

    purge_user(user, acting_user)


user_extension_classes = (UserEthnicityExtension, UserRaceExtension,
                          TimezoneExtension, UserIndigenousStatusExtension)


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


def default_email(context=None):
    """Function to provide a unique, default email if none is provided

    :param context: is populated by SQLAlchemy - see Context-Sensitive default
        functions in http://docs.sqlalchemy.org/en/latest/core/defaults.html

    :return: a unique email string to avoid unique constraints, if an email
        isn't provided in the context

    """
    value = None
    if context:
        value = context.current_parameters.get('email')
    if not value or value == NO_EMAIL_PREFIX:
        value = NO_EMAIL_PREFIX + str(time.time())
    return value


class User(db.Model, UserMixin):
    # PLEASE maintain merge_with() as user model changes #
    __tablename__ = 'users'  # Override default 'user'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    registered = db.Column(db.DateTime, default=datetime.utcnow)
    _email = db.Column(
        'email', db.String(120), unique=True, nullable=False,
        default=default_email)
    phone_id = db.Column(db.Integer, db.ForeignKey('contact_points.id',
                                                   ondelete='cascade'))
    alt_phone_id = db.Column(db.Integer, db.ForeignKey('contact_points.id',
                                                       ondelete='cascade'))
    gender = db.Column('gender', gender_types)
    birthdate = db.Column(db.Date)
    image_url = db.Column(db.Text)
    active = db.Column(
        'is_active', db.Boolean(), nullable=False, server_default='1')
    locale_id = db.Column(db.ForeignKey('codeable_concepts.id'))
    timezone = db.Column(db.String(20), default='UTC')
    deleted_id = db.Column(
        db.ForeignKey('audit.id', use_alter=True,
                      name='user_deleted_audit_id_fk'), nullable=True)
    deceased_id = db.Column(
        db.ForeignKey('audit.id', use_alter=True,
                      name='user_deceased_audit_id_fk'), nullable=True)
    practitioner_id = db.Column(db.ForeignKey('practitioners.id'))

    # We use email like many traditional systems use username.
    # Create a synonym to simplify integration with other libraries (i.e.
    # flask-user).  Effectively makes the attribute email avail as username
    username = synonym('email')

    # Only used for local accounts
    password = db.Column(db.String(255))
    reset_password_token = db.Column(db.String(100))
    confirmed_at = db.Column(db.DateTime())

    user_audits = db.relationship('Audit', cascade='delete',
                                  foreign_keys=[Audit.user_id])
    subject_audits = db.relationship('Audit', cascade='delete',
                                     foreign_keys=[Audit.subject_id])
    auth_providers = db.relationship('AuthProvider', lazy='dynamic',
                                     cascade='delete')
    _consents = db.relationship('UserConsent', lazy='dynamic',
                                cascade='delete')
    indigenous = db.relationship(Coding, lazy='dynamic',
                                 secondary="user_indigenous")
    encounters = db.relationship('Encounter', cascade='delete')
    ethnicities = db.relationship(Coding, lazy='dynamic',
                                  secondary="user_ethnicities")
    groups = db.relationship('Group', secondary='user_groups',
                             backref=db.backref('users', lazy='dynamic'))
    interventions = db.relationship(
        'Intervention',
        lazy='dynamic',
        secondary="user_interventions",
        backref=db.backref('users'))
    questionnaire_responses = db.relationship('QuestionnaireResponse',
                                              lazy='dynamic', cascade='delete')
    races = db.relationship(Coding, lazy='dynamic',
                            secondary="user_races")
    observations = db.relationship(
        'Observation',
        lazy='dynamic',
        secondary="user_observations",
        backref=db.backref('users'))
    organizations = db.relationship(
        'Organization',
        lazy='dynamic',
        secondary="user_organizations",
        backref=db.backref('users'))
    procedures = db.relationship('Procedure', lazy='dynamic',
                                 backref=db.backref('user'), cascade='delete')
    roles = db.relationship('Role', secondary='user_roles',
                            backref=db.backref('users', lazy='dynamic'))
    _locale = db.relationship(CodeableConcept, cascade="save-update")
    deleted = db.relationship('Audit', cascade="save-update",
                              foreign_keys=[deleted_id])
    deceased = db.relationship('Audit', cascade="save-update",
                               foreign_keys=[deceased_id])
    documents = db.relationship('UserDocument', lazy='dynamic',
                                cascade='save-update, delete')
    _identifiers = db.relationship(
        'Identifier', lazy='dynamic', secondary='user_identifiers')

    _phone = db.relationship('ContactPoint', foreign_keys=phone_id,
                             cascade="save-update, delete")
    _alt_phone = db.relationship('ContactPoint', foreign_keys=alt_phone_id,
                                 cascade="save-update, delete")
    notifications = db.relationship(
        'Notification', secondary='user_notifications',
        backref=db.backref('users', lazy='dynamic'))

    ###
    # PLEASE maintain merge_with() as user model changes #
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
            name = ' '.join((self.first_name, self.last_name))
        else:
            name = self.username
        return escape(name) if name else None

    @property
    def current_encounter(self):
        """Shortcut to current encounter, if present

        An encounter is typically bound to the logged in user, not
        the subject, if a different user is performing the action.
        """
        query = Encounter.query.filter(Encounter.user_id == self.id).filter(
            Encounter.status == 'in-progress')
        if query.count() == 0:
            return None
        if query.count() != 1:
            # Not good - we should only have one `active` encounter for
            # the current user.  Log details for debugging and return the
            # first
            msg = "Multiple active encounters found for {}: {}".format(
                self,
                [(e.status, str(e.start_time), str(e.end_time))
                 for e in query])
            current_app.logger.error(msg)
        return query.first()

    @property
    def locale(self):
        if self._locale and self._locale.codings and (
                len(self._locale.codings) > 0):
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
        # IETF BCP 47 standard uses hyphens, but we instead store w/
        # underscores, to better integrate with babel/LR URLs/etc
        data = {"coding": [{'code': lang_info[0], 'display': lang_info[1],
                            'system': IETF_LANGUAGE_TAG}]}
        self._locale = CodeableConcept.from_fhir(data)

    @hybrid_property
    def email(self):
        # Called in different contexts - only compare string
        # value if it's a base string type, as opposed to when
        # its being used in a query statement (email.ilike('foo'))
        if isinstance(self._email, basestring):
            if self._email.startswith(INVITE_PREFIX):
                # strip the invite prefix for UI
                return self._email[len(INVITE_PREFIX):]

            if self._email.startswith(NO_EMAIL_PREFIX):
                # return None as we don't have an email
                return None

            if self._email.startswith(DELETED_PREFIX[:10]):
                match = regex.match(DELETED_REGEX, self._email)
                if not match:
                    raise ValueError(
                        "Apparently deleted user's email doesn't fit "
                        "expected pattern {}".format(self))
                return match.groups()[0]

        return self._email

    @email.setter
    def email(self, email):
        if email == NO_EMAIL_PREFIX:
            self._email = default_email()
        elif self._email and self._email.startswith(
                NO_EMAIL_PREFIX) and not email:
            # already a unique email, for a user w/o email, don't
            # set to an empty string if they didn't give a value.
            pass
        else:
            self._email = email
        assert(self._email and len(self._email))

    @property
    def phone(self):
        if self._phone:
            return self._phone.value

    @phone.setter
    def phone(self, val):
        if self._phone:
            if val:
                self._phone.value = val
            else:
                self._phone = None
        elif val:
            self._phone = ContactPoint(
                system='phone', use='mobile', value=val)

    @property
    def alt_phone(self):
        if self._alt_phone:
            return self._alt_phone.value

    @alt_phone.setter
    def alt_phone(self, val):
        if self._alt_phone:
            if val:
                self._alt_phone.value = val
            else:
                self._alt_phone = None
        elif val:
            self._alt_phone = ContactPoint(
                system='phone', use='home', value=val)

    def mask_email(self, prefix=INVITE_PREFIX):
        """Mask temporary account email to avoid collision with registered

        Temporary user accounts created for the purpose of invites get
        in the way of the user creating a registered account.  Add a hidden
        prefix to the email address in the temporary account to avoid
        collision.

        """
        # Don't apply the invite mask to a user without email
        if prefix == INVITE_PREFIX and self._email.startswith(NO_EMAIL_PREFIX):
            return

        if self._email:
            if not self._email.startswith(prefix):
                self._email = prefix + self._email
        else:
            self._email = prefix

    @property
    def identifiers(self):
        """Return list of identifiers

        Several identifiers are "implicit", such as the primary key
        from the user table, and any auth_providers associated with
        this user.  Add those if not already found for this user
        on request, and return with existing identifiers linked
        with this account.

        """
        primary = Identifier(use='official', system=TRUENTH_ID, value=self.id)
        if primary not in self._identifiers.all():
            self._identifiers.append(primary)

        if self.username:
            # As email addresses do legitimately change when registering and
            # deleting users, may need to update the existing Identifier
            username_identifier = [
                i for i in self._identifiers if i.system == TRUENTH_USERNAME]
            if len(username_identifier) > 1:
                raise ValueError(
                    "Users should only have a single identifier with system {}."
                    "Problem user: {}".format(TRUENTH_USERNAME, self))
            if username_identifier:
                if username_identifier[0].value != self._email:
                    username_identifier[0].value = self._email
            else:
                secondary = Identifier(
                    use='secondary', system=TRUENTH_USERNAME, value=self._email)
                self._identifiers.append(secondary)

        for provider in self.auth_providers:
            p_id = Identifier.from_fhir(provider.as_fhir())
            if p_id not in self._identifiers.all():
                self._identifiers.append(p_id)

        return self._identifiers

    @property
    def external_study_id(self):
        """Return the value of the user's external study identifier(s)

        If more than one external study identifiers are found for the user,
        values will be joined by ', '

        """
        ext_ids = self._identifiers.filter_by(
            system=TRUENTH_EXTERNAL_STUDY_SYSTEM)
        if ext_ids.count():
            return ', '.join([ext_id.value for ext_id in ext_ids])

    @property
    def org_coding_display_options(self):
        """Collates all race/ethnicity/indigenous display options
        from the user's orgs to establish which options to display"""
        options = {}
        orgs = self.organizations
        if orgs:
            options['race'] = any(o.race_codings for o in orgs)
            options['ethnicity'] = any(o.ethnicity_codings for o in orgs)
            options['indigenous'] = any(o.indigenous_codings for o in orgs)
        else:
            attrs = ('race', 'ethnicity', 'indigenous')
            options = dict.fromkeys(attrs, True)
        return options

    @property
    def locale_display_options(self):
        """Collates all the locale options from the user's orgs
        to establish which should be visible to the user"""

        def locale_name_from_code(locale_code):
            coding = Coding.query.filter_by(system=IETF_LANGUAGE_TAG, code=locale_code).first()
            return coding.display

        locale_options = {}
        if self.locale_code:
            locale_options[self.locale_code] = self.locale_name
        for org in self.organizations:
            for locale in org.locales:
                locale_options[locale.code] = locale.display
            if org.default_locale and org.default_locale not in locale_options:
                locale_options[org.default_locale] = locale_name_from_code(org.default_locale)
            while org.partOf_id:
                org = Organization.query.get(org.partOf_id)
                for locale in org.locales:
                    locale_options[locale.code] = locale.display
                if org.default_locale and org.default_locale not in locale_options:
                    locale_options[org.default_locale] = locale_name_from_code(org.default_locale)

        return locale_options

    def add_organization(self, organization_name):
        """Shortcut to add a clinic/organization by name"""
        org = Organization.query.filter_by(name=organization_name).one()
        if org not in self.organizations:
            self.organizations.append(org)

    def first_top_organization(self):
        """Return first top level organization for user

        NB, none of the above doesn't count and will not be retuned.

        A user may have any number of organizations, but most business
        decisions, assume there is only one.  Arbitrarily returning the
        first from the matchin query in case of multiple.

        :returns: a single top level organization, or None

        """
        top_orgs = OrgTree().find_top_level_org(self.organizations)
        if top_orgs:
            return top_orgs[0]
        return None

    def leaf_organizations(self):
        """Return list of 'leaf' organization ids for user's orgs

        Users, especially staff, have arbitrary number of organization
        associations, at any level of the organization hierarchy.  This
        method looks up all child leaf nodes from the users existing orgs.

        """
        leaves = set()
        OT = OrgTree()
        if self.organizations:
            for org in self.organizations:
                if org.id == 0:
                    continue
                leaves.update(OT.all_leaves_below_id(org.id))
            return list(leaves)
        else:
            return None

    def add_observation(self, fhir, audit):
        if 'coding' not in fhir['code']:
            return 400, "requires at least one CodeableConcept"
        if 'valueQuantity' not in fhir:
            return 400, "missing required 'valueQuantity'"

        cc = CodeableConcept.from_fhir(fhir['code']).add_if_not_found()

        v = fhir['valueQuantity']
        vq = ValueQuantity(value=v.get('value'),
                           units=v.get('units'),
                           system=v.get('system'),
                           code=v.get('code')).add_if_not_found(True)

        issued = fhir.get('issued') and\
            parser.parse(fhir.get('issued')) or None
        observation = self.save_observation(cc, vq, audit, issued)
        if 'performer' in fhir:
            for p in fhir['performer']:
                performer = Performer.from_fhir(p)
                observation.performers.append(performer)
        return 200, "added {} to user {}".format(observation, self.id)

    def add_relationship(self, other_user, relationship_name):
        # confirm it's not already defined
        relationship = Relationship.query.filter_by(
            name=relationship_name).first()
        existing = UserRelationship.query.filter_by(
            user_id=self.id,
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

        return [obs.value_quantity for obs in self.observations if
                obs.codeable_concept_id == codeable_concept.id]

    def fetch_datetime_for_concept(self, codeable_concept):
        """Return newest issued timestamp from matching observation"""
        codeable_concept = codeable_concept.add_if_not_found()
        matching_observations = [
            obs for obs in self.observations if
            obs.codeable_concept_id == codeable_concept.id]
        if not matching_observations:
            return None
        newest = max(o.issued for o in matching_observations
                     if o.issued is not None)
        return newest

    def save_constrained_observation(
            self, codeable_concept, value_quantity, audit, issued=None):
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

        existing = [obs for obs in self.observations if
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

        self.save_observation(codeable_concept, value_quantity, audit, issued)

    def save_observation(self, cc, vq, audit, issued):
        """Helper method for creating new observations"""
        # avoid cyclical imports
        from .assessment_status import invalidate_assessment_status_cache

        observation = Observation(
            codeable_concept_id=cc.id,
            issued=issued,
            value_quantity_id=vq.id).add_if_not_found(True)
        # The audit defines the acting user, to which the current
        # encounter is attached.
        encounter = get_user(audit.user_id).current_encounter
        UserObservation(user_id=self.id, encounter=encounter, audit=audit,
                        observation_id=observation.id).add_if_not_found()
        invalidate_assessment_status_cache(self.id)
        return observation

    def clinical_history(self, requestURL=None):
        now = datetime.utcnow()
        fhir = {"resourceType": "Bundle",
                "title": "Clinical History",
                "link": [{"rel": "self", "href": requestURL}, ],
                "updated": as_fhir(now),
                "entry": []}

        for ob in self.observations:
            fhir['entry'].append({"title": "Patient Observation",
                                  "updated": as_fhir(now),
                                  "author": [{"name": "Truenth Portal"}, ],
                                  "content": ob.as_fhir()})
        return fhir

    def procedure_history(self, requestURL=None):
        now = datetime.utcnow()
        fhir = {"resourceType": "Bundle",
                "title": "Procedure History",
                "link": [{"rel": "self", "href": requestURL}, ],
                "updated": as_fhir(now),
                "entry": []}

        for proc in self.procedures:
            fhir['entry'].append({"resource": proc.as_fhir()})
        return fhir

    def as_fhir(self, include_empties=True):
        """Return JSON representation of user

        :param include_empties: if True, returns entire object definition;
            if False, empty elements are removed from the result
        :return: JSON representation of a FHIR Patient resource

        """
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
        d['identifier'] = [id.as_fhir() for id in self.identifiers]
        d['name'] = {}
        d['name']['given'] = self.first_name
        d['name']['family'] = self.last_name
        d['birthDate'] = as_fhir(self.birthdate) if self.birthdate else None
        d.update(deceased())
        d['gender'] = self.gender
        d['status'] = 'registered' if self.registered else 'unknown'
        d['communication'] = (
            [{"language": self._locale.as_fhir()}] if self._locale else None)
        telecom = Telecom(email=self.email,
                          contact_points=[self._phone, self._alt_phone])
        d['telecom'] = telecom.as_fhir()
        d['photo'] = []
        if self.image_url:
            d['photo'].append({'url': self.image_url})
        extensions = []
        for kls in user_extension_classes:
            instance = user_extension_map(self, {'url': kls.extension_url})
            data = instance.as_fhir(include_empties)
            if data:
                extensions.append(data)
        d['extension'] = extensions
        d['careProvider'] = careProviders()
        if self.practitioner_id:
            d['careProvider'].append(reference.Reference.practitioner(
                self.practitioner_id).as_fhir())
        d['deleted'] = (
            FHIR_datetime.as_fhir(self.deleted.timestamp)
            if self.deleted_id else None)
        if not include_empties:
            return strip_empties(d)
        return d

    def update_consents(self, consent_list, acting_user):
        """Update user's consents

        Adds the provided list of consent agreements to the user.
        If the user had pre-existing consent agreements between the
        same organization_id, the new will replace the old

        """
        delete_consents = []  # capture consents being replaced
        for consent in consent_list:
            # add audit for consent signed date
            audit = Audit(
                user_id=acting_user.id,
                subject_id=self.id,
                comment="Consent agreement signed",
                context='consent')
            # Look for existing consent for this user/org
            for existing_consent in self.valid_consents:
                if existing_consent.organization_id == int(
                        consent.organization_id):
                    current_app.logger.debug("deleting matching consent {} "
                                             "replacing with {} ".format(
                                                 existing_consent, consent))
                    delete_consents.append(existing_consent)

            if hasattr(consent, 'acceptance_date'):
                # Move data to where it belongs, in the audit row
                audit.timestamp = consent.acceptance_date
                del consent.acceptance_date

            consent.audit = audit
            db.session.add(consent)
            db.session.commit()
            audit, consent = map(db.session.merge, (audit, consent))
            # update consent signed audit with consent ID ref
            audit.comment = "Consent agreement {} signed".format(consent.id)
            # add audit for consent recorded date
            recorded = Audit(
                user_id=acting_user.id,
                subject_id=self.id,
                comment="Consent agreement {} recorded".format(consent.id),
                context='consent',
                timestamp=datetime.utcnow())
            db.session.add(audit)
            db.session.add(recorded)
            db.session.commit()

        for replaced in delete_consents:
            replaced.deleted = Audit(
                comment="new consent replacing existing",
                user_id=current_user().id,
                subject_id=self.id, context='consent')
            replaced.status = "deleted"
            db.session.add(replaced)
        db.session.commit()

    def deactivate_tous(self, acting_user, types=None):
        """ Mark user's current active ToU agreements as inactive

        Marks the user's current active ToU agreements as inactive.
        User must agree to ToUs again upon next login (per CoreData logic).
        If types provided, only deactivates agreements of that ToU type.
        Called when the ToU agreement language is updated.

        :param acting_user: user behind the request for permission checks
        :param types: ToU types for which to invalide agreements (optional)

        """
        from .tou import ToU

        for tou in ToU.query.join(Audit).filter(and_(
                Audit.subject_id == self.id,
                ToU.active.is_(True))):
            if not types or (tou.type in types):
                tou.active = False
                audit = Audit(
                    user_id=acting_user.id,
                    subject_id=self.id,
                    comment=("ToU agreement {} marked as "
                             "inactive".format(tou.id)),
                    context='tou',
                    timestamp=datetime.utcnow())
                db.session.add(tou)
                db.session.add(audit)
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
            """staff can not modify their own org affiliation at all

            as per
            https://www.pivotaltracker.com/n/projects/1225464/stories/133286317
            raise exception if staff or staff-admin  is attempting to
            change their own org affiliations.

            """
            if (not acting_user.has_role(ROLE.ADMIN)
                and (acting_user.has_role(ROLE.STAFF)
                     or acting_user.has_role(ROLE.STAFF_ADMIN))
                    and user.id == acting_user.id):
                raise ValueError(
                    "staff can't change their own organization affiliations")
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
                        role, self.id), user_id=acting_user.id,
                    subject_id=self.id, context='role')
                db.session.add(audit)

        for stale_role in remove_if_not_requested.values():
            self.roles.remove(stale_role)
            audit = Audit(
                comment="deleted {} from user {}".format(
                    stale_role, self.id), user_id=acting_user.id,
                subject_id=self.id, context='role')
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

        def v_or_first(value, field_name):
            """Return desired from list or scalar value

            :param value: the raw data, may be a single value (directly
             returned) or a list from which the first element will be returned
            :param field_name: used in error text when multiple values
             are found for a constrained item.

            Some fields, such as `name` were assumed to always be a single
            dictionary containing single values, whereas the FHIR spec
            defines them to support 0..* meaning we must handle a list.

            NB - as the datamodel still only expects one, a 400 will be
            raised if given multiple values, using the `field_name` in the text.

            """
            if isinstance(value, (tuple, list)):
                if len(value) > 1:
                    msg = "Can't handle multiple values for `{}`".format(field_name)
                    current_app.logger.warn(msg)
                    abort(400, msg)
                return value[0]
            return value

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
                    subject_id=self.id, context='user',
                    comment="time of death for user {}".format(self.id))
                self.deceased = audit
            elif 'deceasedBoolean' in fhir:
                if fhir['deceasedBoolean'] is False:
                    if self.deceased_id:
                        # Remove deceased record from the user, but maintain
                        # the old audit row.
                        self.deceased_id = None
                        audit = Audit(
                            user_id=current_user().id,
                            subject_id=self.id, context='user',
                            comment=("Remove existing deceased from "
                                     "user {}".format(self.id)))
                        db.session.add(audit)
                else:
                    # still marked with an audit, but without the special
                    # comment syntax and using default (current) time.
                    audit = Audit(
                        user_id=current_user().id, subject_id=self.id,
                        comment=("Marking user {} as "
                                 "deceased".format(self.id)), context='user')
                    self.deceased = audit

        def update_identifiers(fhir):
            """Given FHIR defines identifiers, but we never remove implicit

            Implicit identifiers include user.id, user.email (username)
            and any auth_providers.  Others may be manipulated via
            this function like any PUT interface, where the given values
            are conclusive - deleting unmentioned and adding new.

            """
            if 'identifier' not in fhir:
                return

            # ignore internal system identifiers
            pre_existing = [ident for ident in self._identifiers
                            if ident.system not in internal_identifier_systems]
            seen = []
            for identifier in fhir['identifier']:
                try:
                    new_id = Identifier.from_fhir(identifier)
                    if new_id in seen:
                        abort(400, 'Duplicate identifiers found, should be unique set')
                    seen.append(new_id)
                except KeyError as e:
                    abort(400, "{} field not found for identifier".format(e))
                except TypeError as e:
                    abort(400, "invalid format for identifier {}".format(e))
                if new_id.system in internal_identifier_systems:
                    continue
                new_id = new_id.add_if_not_found()
                if new_id in pre_existing:
                    pre_existing.remove(new_id)
                else:
                    self._identifiers.append(new_id)

            # remove any pre existing that were not mentioned
            for unmentioned in pre_existing:
                self._identifiers.remove(unmentioned)

        def update_care_providers(fhir):
            """Update user fields based on careProvider Reference types"""
            org_list = []
            for cp in fhir.get('careProvider'):
                parsed = reference.Reference.parse(cp)
                if type(parsed) is Organization:
                    org_list.append(parsed)
                elif type(parsed) is Practitioner:
                    self.practitioner_id = parsed.id
            self.update_orgs(org_list, acting_user)

        if 'name' in fhir:
            name = v_or_first(fhir['name'], 'name')
            self.first_name = v_or_n(
                v_or_first(name.get('given'), 'given name')
            ) or self.first_name
            self.last_name = v_or_n(
                v_or_first(name.get('family'), 'family name')
            ) or self.last_name
        if 'birthDate' in fhir:
            try:
                bd = fhir['birthDate']
                self.birthdate = datetime.strptime(
                    bd.strip(), '%Y-%m-%d') if bd else None
            except (AttributeError, ValueError):
                abort(400, "birthDate '{}' doesn't match expected format "
                      "'%Y-%m-%d'".format(fhir['birthDate']))
        update_deceased(fhir)
        update_identifiers(fhir)
        update_care_providers(fhir)
        if 'gender' in fhir:
            self.gender = fhir['gender'].lower() if fhir['gender'] else None
        if 'telecom' in fhir:
            telecom = Telecom.from_fhir(fhir['telecom'])
            if telecom.email:
                if ((telecom.email != self.email) and
                        (User.query.filter_by(email=telecom.email).count() > 0)):
                    abort(400, "email address already in use")
                self.email = telecom.email
            telecom_cps = telecom.cp_dict()
            self.phone = telecom_cps.get(('phone', 'mobile')) \
                or telecom_cps.get(('phone', None))
            self.alt_phone = telecom_cps.get(('phone', 'home'))
        if fhir.get('communication'):
            for e in fhir['communication']:
                if 'language' in e:
                    self._locale = CodeableConcept.from_fhir(e.get('language'))
        if 'extension' in fhir:
            # a number of elements live in extension - handle each in turn
            for e in fhir['extension']:
                instance = user_extension_map(self, e)
                instance.apply_fhir()

    @classmethod
    def column_names(cls):
        return [prop.key for prop in class_mapper(cls).iterate_properties
                if isinstance(prop, ColumnProperty)]

    def merge_with(self, other_id):
        """merge details from other user into self

        Primary usage stems from different account registration flows.
        For example, users are created when invited by staff to participate,
        and when the same user later opts to register, a second account
        is generated during the registration process (either by flask-user
        or other mechanisms like add_authomatic_user).

        NB - caller MUST manage email due to unique constraints

        """
        other = User.query.get(other_id)
        if not other:
            abort(404, 'other_id {} not found'.format(other_id))

        # direct attributes on user
        # intentionally skip {id, email, reset_password_token, timezone}
        # as we prefer the original values for these during account promotion
        exclude = ['id', '_email', 'reset_password_token', 'timezone']
        for attr in (col for col in self.column_names() if col not in exclude):
            if not getattr(other, attr):
                continue
            setattr(self, attr, getattr(other, attr))

        # n-to-n relationships on user
        for relationship in ('organizations', '_consents', 'procedures',
                             'observations', 'relationships', 'roles',
                             'races', 'ethnicities', 'groups',
                             'questionnaire_responses', '_identifiers'):
            self_entity = getattr(self, relationship)
            other_entity = getattr(other, relationship)
            if relationship == 'roles':
                # We don't copy over the roles used to mark the weak account
                append_list = [item for item in other_entity if item not in
                               self_entity and item.name not in
                               ('write_only',
                                'promote_without_identity_challenge')]
            elif relationship == '_identifiers':
                # Don't copy internal identifiers
                append_list = [item for item in other_entity if item not in
                               self_entity and item.system not in
                               internal_identifier_systems]
            else:
                append_list = [item for item in other_entity if item not in
                               self_entity]
            for item in append_list:
                self_entity.append(item)

    def promote_to_registered(self, registered_user):
        """Promote a weakly authenticated account to a registered one"""
        assert self.id != registered_user.id
        before = self.as_fhir()

        # due to unique constraints, email is handled manually after
        # registered_user is deleted (when email gets masked)
        registered_email = registered_user.email

        self.merge_with(registered_user.id)

        # remove special roles from invited user, if present
        self.update_roles(
            [role for role in self.roles if role.name not in (
                ROLE.WRITE_ONLY, ROLE.PROMOTE_WITHOUT_IDENTITY_CHALLENGE)],
            acting_user=self)

        # delete temporary registered user account
        registered_user.delete_user(acting_user=self)

        # restore email and record event
        self.email = registered_email
        self.registered = datetime.utcnow()
        after = self.as_fhir()
        details = StringIO()
        dict_match(newd=after, oldd=before, diff_stream=details)
        db.session.add(Audit(
            comment="registered invited user, {}".format(details.getvalue()),
            user_id=self.id, subject_id=self.id,
            context='account'))

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

        orgtree = OrgTree()
        if any(self.has_role(r) for r in (ROLE.STAFF, ROLE.STAFF_ADMIN)
               ) and other.has_role(ROLE.PATIENT):
            # Staff has full access to all patients with a valid consent
            # at or below the same level of the org tree as the staff has
            # associations with.  Furthermore, a patient may have a consent
            # agreement at a higher level in the orgtree than the staff member,
            # in which case the patient's organization must be a child
            # of the staff's organization for access.

            # As long as the consent is valid (not expired or deleted) it's
            # adequate for 'view'.  'edit' requires the staff_editable option
            # on the consent.
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
            # Still here implies time to check 'furthermore' clause
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

        if self.has_role(ROLE.STAFF_ADMIN) and other.has_role(ROLE.STAFF):
            # Staff admin can do anything to staff at or below their level
            for sa_org in self.organizations:
                others_ids = [o.id for o in other.organizations]
                if orgtree.at_or_below_ids(sa_org.id, others_ids):
                    return True

        if self.has_role(
                ROLE.INTERVENTION_STAFF) and other.has_role(
                ROLE.PATIENT):
            # Intervention staff can access patients within that intervention
            for intervention in self.interventions:
                if intervention in other.interventions:
                    return True

        abort(401, "Inadequate role for {} of {}".format(permission, other_id))

    def has_role(self, role_name):
        return role_name in [r.name for r in self.roles]

    def staff_html(self):
        """Helper used from templates to display any custom staff/provider text

        Interventions can add personalized HTML for care staff
        to consume on the /patients list.  Look up any values for this user
        on all interventions.

        """
        uis = UserIntervention.query.filter(and_(
            UserIntervention.user_id == self.id,
            UserIntervention.staff_html.isnot(None)))
        if uis.count() == 0:
            return ""
        if uis.count() == 1:
            return uis[0].staff_html
        else:
            return '<div>' + '</div><div>'.join(
                [ui.staff_html for ui in uis]) + '</div>'

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
        if (birthdate.year < 1900 or
                dob.strftime('%d%m%Y') != birthdate.strftime('%d%m%Y')):
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
        from .auth import Client, Token

        if self == acting_user:
            raise ValueError("can't delete self")
        if self is None or acting_user is None:
            raise ValueError("both user and acting_user must be well defined")

        # Don't allow deletion of users with client applications
        clients = Client.query.filter_by(user_id=self.id)
        if clients.count():
            raise ValueError(
                "Users owning client applications can not "
                "be deleted.  Delete client apps first: {}".format(
                    [client.id for client in clients]))

        self.active = False
        self.mask_email(prefix=DELETED_PREFIX.format(time=int(time.time())))
        self.deleted = Audit(user_id=acting_user.id, subject_id=self.id,
                             comment="marking deleted {}".format(self),
                             context='account')
        # also need to alter the TRUENTH_USERNAME identifier in case anyone
        # in the future needs to reuse this address
        ids = [id for id in self._identifiers if id.system == TRUENTH_USERNAME]
        if ids:
            ids[0].value = self._email

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
    if session and ('id' in session):
        # Locally logged in
        uid = session['id']
    elif (flask_login_current_user and
          _call_or_get(flask_login_current_user.is_authenticated)):
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
    user_id = db.Column(
        db.Integer(),
        db.ForeignKey(
            'users.id',
            ondelete='CASCADE'),
        nullable=False)
    role_id = db.Column(
        db.Integer(),
        db.ForeignKey(
            'roles.id',
            ondelete='CASCADE'),
        nullable=False)

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
    user_id = db.Column(
        db.Integer(),
        db.ForeignKey(
            'users.id',
            ondelete='CASCADE'),
        nullable=False)
    other_user_id = db.Column(
        db.Integer(),
        db.ForeignKey(
            'users.id',
            ondelete='CASCADE'),
        nullable=False)
    relationship_id = db.Column(
        db.Integer(),
        db.ForeignKey(
            'relationships.id',
            ondelete='CASCADE'),
        nullable=False)

    user = db.relationship("User", backref='relationships',
                           foreign_keys=[user_id])
    other_user = db.relationship("User",
                                 foreign_keys=[other_user_id])
    relationship = db.relationship("Relationship",
                                   foreign_keys=[relationship_id])

    __table_args__ = (
        UniqueConstraint(
            'user_id',
            'other_user_id',
            'relationship_id',
            name='_user_relationship'),
    )

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "{0.relationship} between {0.user_id} and "\
            "{0.other_user_id}".format(self)
