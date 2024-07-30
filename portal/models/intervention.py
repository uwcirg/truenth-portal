"""Intervention Module"""
from flask import current_app
from sqlalchemy import Enum, and_
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import BadRequest

from ..database import db
from ..dict_tools import strip_empties
from .lazy import query_by_name
from .role import ROLE

LOGOUT_EVENT = 0b001
USER_DOC_EVENT = 0b010


class DisplayDetails(object):
    """Simple abstraction to communicate display details to front end

    To provide a custom experience, intevention access can be set at
    several levels.  For a user, access is either available or not, and when
    available, the link controls may be intentionally disabled for a reason the
    intervention should note in the status_text field.

    Attributes::
        access: {True, False}
        card_html: Text to display on the card
        link_label: Text used to label the button or hyperlink
        link_url: URL for the button or link - link to be disabled when null
        status_text: Text to inform user of status, or why it's disabled

    """

    def __init__(self, access, intervention, user_intervention):
        """Build best set available, prefering values in user_intervention"""
        ui = user_intervention
        self.access = access
        self.card_html = ui and ui.card_html or intervention.card_html
        self.link_label = ui and ui.link_label or intervention.link_label
        self.link_url = ui and ui.link_url or intervention.link_url
        self.status_text = ui and ui.status_text or intervention.status_text


class Intervention(db.Model):
    __tablename__ = 'interventions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    # nullable as interventions may not have a valid client
    client_id = db.Column(db.ForeignKey('clients.client_id'))
    card_html = db.Column(db.Text)
    link_label = db.Column(db.Text)
    link_url = db.Column(db.Text)
    status_text = db.Column(db.Text)
    public_access = db.Column(db.Boolean, default=True)
    display_rank = db.Column(db.Integer)
    subscribed_events = db.Column(db.Integer, nullable=False, default=0)

    client = db.relationship(
        'Client',
        primaryjoin="Client.client_id==Intervention.client_id",
        uselist=False, backref='Client')

    access_strategies = db.relationship(
        'AccessStrategy', order_by="AccessStrategy.rank")

    @hybrid_property
    def subscribed_to_logout_event(self):
        return self.subscribed_events & LOGOUT_EVENT

    @subscribed_to_logout_event.setter
    def subscribed_to_logout_event(self, value):
        if value:
            self.subscribed_events = self.subscribed_events | LOGOUT_EVENT
        else:
            self.subscribed_events = self.subscribed_events & ~LOGOUT_EVENT

    @hybrid_property
    def subscribed_to_user_doc_event(self):
        return self.subscribed_events & USER_DOC_EVENT

    @subscribed_to_user_doc_event.setter
    def subscribed_to_user_doc_event(self, value):
        if value:
            self.subscribed_events = self.subscribed_events | USER_DOC_EVENT
        else:
            self.subscribed_events = self.subscribed_events & ~USER_DOC_EVENT

    def as_json(self):
        """Returns the 'safe to export' portions of an intervention

        The client_id and link_url are non-portable between systems.
        The id is also independent - return the rest of the not null
        fields as a simple json dict.

        NB for staging exclusions to function, link_url and client_id
        are now included. Take care to remove it from persistence files
        where it is NOT portable, for example, when generating persistence
        files programmatically.

        """
        d = {'resourceType': 'Intervention'}
        for attr in ('name', 'description', 'card_html', 'link_label',
                     'status_text', 'public_access', 'display_rank',
                     'subscribed_events', 'link_url', 'client_id'):
            if getattr(self, attr, None) is not None:
                d[attr] = getattr(self, attr)

        return d

    @staticmethod
    def rct_ids():
        """returns list of RCT (randomized control trial) intervention ids"""
        names = current_app.config.get('RCT_INTERVENTIONS')
        if not names:
            return None
        ids = [i.id for i in Intervention.query.filter(
            Intervention.name.in_(names))]
        if len(ids) != len(names):
            raise ValueError(
                "can't locate all interventions named in config "
                "'RCT_INTERVENTIONS': {}".format(names))
        return ids

    @classmethod
    def from_json(cls, data):
        intervention = cls()
        return intervention.update_from_json(data)

    def update_from_json(self, data):
        if 'name' not in data:
            raise ValueError("required 'name' field not found")

        for attr in ('name', 'description', 'card_html', 'link_label',
                     'status_text', 'public_access', 'display_rank',
                     'subscribed_events'):
            if attr in data:
                setattr(self, attr, data.get(attr))

        # link_url and client_id are special - generally we don't pull
        # from persisted format as each instance is configured to
        # communicate with distinct interventions.  As it is used
        # for prod -> staging, warn if seen on any other system
        if 'link_url' in data and self.link_url != data['link_url']:
            if current_app.config.get("SYSTEMT_TYPE", '').lower() != 'staging':
                current_app.logger.warning(
                    "IMPORTING non-portable intervention({}) link_url: '{}'"
                    "".format(self.name, data['link_url']))
            self.link_url = data['link_url']
        if 'client_id' in data and self.client_id != data['client_id']:
            if current_app.config.get("SYSTEMT_TYPE", '').lower() != 'staging':
                current_app.logger.warning(
                    "IMPORTING non-portable intervention({}) client_id: '{}'"
                    "".format(self.name, data['client_id']))
            self.client_id = data['client_id']

        return self

    def fetch_strategies(self):
        """Generator to return each registered strategy

        Strategies need to be brought to life from their persisted
        state.  This generator does so, and returns them in a call
        ready fashion, ordered by the strategy's rank.

        """
        for strat in self.access_strategies:
            func = strat.instantiate()
            yield func

    def display_for_user(self, user):
        """Return the intervention display details for the given user

        Somewhat complicated method, depending on intervention configuration.
        The following ordered steps are used to determine if a user
        should have access to an intervention.  The first 'true' found
        provides access, otherwise the intervention will not be displayed.

        1. call each strategy_function in intervention.access_strategies.
           Note, on rare occasions, a strategy may alter the UserIntervention
           attributes given the circumstances.
        2. check for a UserIntervention row defining access for the given
           user on this intervention.
        3. check if the intervention has `public_access` set

        @return DisplayDetails object defining 'access' and other details
        for how to render the intervention.

        """
        access = False

        # 1. check strategies for access
        for func in self.fetch_strategies():
            if func(intervention=self, user=user):
                access = True
                break

        # 2. check user_intervention for access
        ui = UserIntervention.query.filter_by(
            user_id=user.id, intervention_id=self.id).first()
        if ui and ui.access == 'granted':
            access = True

        # 3. check intervention scope for access
        # (NB - tempting to shortcut by testing this first, but we
        # need to allow all the strategies to run in case they alter settings)
        if self.public_access:
            access = True

        return DisplayDetails(
            access=access, intervention=self, user_intervention=ui)

    def quick_access_check(self, user):
        """Return boolean representing given user's access to intervention

        Somewhat complicated method, depending on intervention configuration.
        The following ordered steps are used to determine if a user
        should have access to an intervention.  The first 'true' found
        is returned (as to make the check as quick as possible).

        1. check if the intervention has `public_access` set
        2. check for a UserIntervention row defining access for the given
           user on this intervention.
        3. call each strategy_function in intervention.access_strategies.

        @return boolean representing 'access'.

        """
        # 1. check intervention scope for access
        if self.public_access:
            return True

        # 2. check user_intervention for access
        ui = UserIntervention.query.filter_by(
            user_id=user.id, intervention_id=self.id).first()
        if ui and ui.access == 'granted':
            return True

        # 3. check strategies for access
        for func in self.fetch_strategies():
            if func.__name__ == 'update_user_card_html':
                return True
            if func(intervention=self, user=user):
                return True

        return False

    def __str__(self):
        """print details needed in audit logs"""
        if self.name == INTERVENTION.DEFAULT.name:
            return ""
        return ("Intervention: {0.description}, "
                "public_access: {0.public_access}, "
                "card_html: {0.card_html}, "
                "link_label: {0.link_label}, "
                "link_url: {0.link_url}, "
                "status_text: {0.status_text},"
                "subscribed_events: {0.subscribed_events}".format(self))


access_types = ('forbidden', 'granted', 'subscribed')
access_types_enum = Enum(*access_types, name='access', create_type=False)


class UserIntervention(db.Model):
    __tablename__ = 'user_interventions'
    id = db.Column(db.Integer, primary_key=True)
    access = db.Column('access', access_types_enum, default='forbidden')
    card_html = db.Column(db.Text)
    staff_html = db.Column(db.Text)
    link_label = db.Column(db.Text)
    link_url = db.Column(db.Text)
    status_text = db.Column(db.Text)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    intervention_id = db.Column(
        db.ForeignKey('interventions.id'), nullable=False)

    def as_json(self, include_empties=True):
        d = {'user_id': self.user_id}
        for field in ('access', 'card_html', 'staff_html',
                      'link_label', 'link_url', 'status_text'):
            d[field] = getattr(self, field)
        if not include_empties:
            return strip_empties(d)
        return d

    def update_from_json(self, data):
        for attr in data:
            setattr(self, attr, data[attr])

    @classmethod
    def user_access_granted(cls, intervention_id, user_id):
        """Shortcut to query for specific (intervention, user) access"""
        q = cls.query.filter(and_(
            cls.user_id == user_id,
            cls.intervention_id == intervention_id,
            cls.access == 'granted'))
        return q.count() > 0


def intervention_restrictions(user):
    """returns tuple of lists for interventions: (disallow, require)

    Users may not have access to some interventions (such as randomized
    control trials).  In such a case, the first of the tuple items
    will name intervention ids which should not be included.

    Other users get access to all patients with one or more
    interventions.  In this case, a list of interventions for which
    the user should be granted access is in the second position.

    :returns disallow, require::
      disallow: list of intervention IDs to exclude associated patients,
        such as the randomized control trial interventions.
      require: list of intervention IDs if patients must also have the
        respective UserIntervention association.

    """
    if user.has_role(ROLE.ADMIN.value):
        return None, None  # no restrictions

    disallowed, required = None, None
    if user.has_role(ROLE.STAFF.value):
        if user.has_role(ROLE.INTERVENTION_STAFF.value):
            raise BadRequest(
                "Patients list for staff and intervention-staff are "
                "mutually exclusive - user shouldn't have both roles")

        # staff users aren't to see patients from RCT interventions
        disallowed = Intervention.rct_ids()
    if user.has_role(ROLE.INTERVENTION_STAFF.value):
        # Look up associated interventions
        uis = UserIntervention.query.filter(
            UserIntervention.user_id == user.id)
        # check if the user is associated with any intervention at all
        if uis.count() == 0:
            raise BadRequest("User is not associated with any intervention.")
        required = [ui.intervention_id for ui in uis]
    return disallowed, required


STATIC_INTERVENTIONS = {
    'analytics': 'Analytics',
    'assessment_engine': 'Assessment Engine',
    'care_plan': 'Care Plan',
    'community_of_wellness': 'Community of Wellness',
    'decision_support_p3p': 'Decision Support P3P',
    'decision_support_wisercare': 'Decision Support WiserCare',
    'music': 'MUSIC Integration',
    'psa_tracker': 'PSA Tracker',
    'self_management': 'Self Management',
    'sexual_recovery': 'Sexual Recovery',
    'social_support': 'Social Support Network',
    'default': 'OTHER: not yet officially supported',
}


def add_static_interventions():
    """Seed database with default static interventions

    Idempotent - run anytime to push any new interventions into existing dbs

    """
    for name, description in STATIC_INTERVENTIONS.items():
        if not Intervention.query.filter_by(name=name).first():
            intervention = Intervention(
                name=name, description=description, card_html=description,
                subscribed_events=LOGOUT_EVENT)
            db.session.add(intervention)


class _NamedInterventions(object):
    """Bunch pattern class to house references to interventions

    Don't use this class directly - make reference to its user,
    the INTERVENTION instance.

    Specialized to handle only Interventions.  Attributes
    (all without a leading '_') assumed to be interventions and may
    be referenced in upper or lower case.

    """

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, query_by_name(Intervention, k))

    def __getattribute__(self, attr):
        if attr.startswith('_'):
            return object.__getattribute__(self, attr)
        # Catch KeyError in case it's a dynamically added intervention
        # (i.e. not from static list)
        try:
            value = self.__dict__[attr.lower()].__call__(self)
        except NoResultFound:
            raise AttributeError("Intervention {} not found".format(attr))
        except KeyError:
            query = Intervention.query.filter_by(name=attr)
            if not query.count():
                raise AttributeError(
                    "Intervention {} not found".format(attr))
            value = query.one()
        return value

    def __iter__(self):
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            try:
                yield getattr(self, attr)
            except AttributeError:
                # Intervention from static list not found in db, skip
                continue

    def __contains__(self, item):
        try:
            self.__getattribute__(item)
            return True
        except AttributeError:
            return False


"""INTERVENTION behaves like a static accessor for all interventions.

Obtain intervention of choice by name in upper or lower case or by string:
    sr = INTERVENTION.SEXUAL_RECOVERY
    sr = INTERVENTION.sexual_recovery
    sr = getattr(INTERVENTION, 'sexual_recovery')

"""
INTERVENTION = _NamedInterventions(**STATIC_INTERVENTIONS)
