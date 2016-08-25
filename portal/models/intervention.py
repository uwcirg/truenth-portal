"""Intervention Module"""
from UserDict import IterableUserDict
from sqlalchemy.dialects.postgresql import ENUM

from ..extensions import db
from .lazy import query_by_name

class DisplayDetails(object):
    """Simple abstraction to communicate display details to front end

    An intervention may be enabled, hidden or disabled.  Furthermore,
    the text displayed and where the links point to might be configured
    per user for any intervention.

    Attributes::
        access: {enabled, disabled or hidden}
        card_html: Text to display on the card
        link_label: Text used to label the button or hyperlink
        link_url: URL for the button or link
        status_text: Text to inform user status, or why it's disabled

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
    client_id = db.Column(db.ForeignKey('clients.client_id'))
    card_html = db.Column(db.Text)
    link_label = db.Column(db.Text)
    link_url = db.Column(db.Text)
    status_text = db.Column(db.Text)
    public_access = db.Column(db.Boolean, default=True)

    client = db.relationship('Client',
        primaryjoin="Client.client_id==Intervention.client_id",
        uselist=False, backref='Client')

    access_strategies = db.relationship(
        'AccessStrategy', order_by="AccessStrategy.rank")

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

        return DisplayDetails(access=access, intervention=self,
                user_intervention=ui)

    def __str__(self):
        """print details needed in audit logs"""
        if self.name == INTERVENTION.DEFAULT.name:
            return ""
        return ("Intervention: {0.description}, "
                "public_access: {0.public_access}, "
                "card_html: {0.card_html}, "
                "link_label: {0.link_label}, "
                "link_url: {0.link_url}, "
                "status_text: {0.status_text}".format(self))


access_types = ENUM('forbidden', 'granted', name='access',
                    create_type=False)


class UserIntervention(db.Model):
    __tablename__ = 'user_interventions'
    id = db.Column(db.Integer, primary_key=True)
    access = db.Column('access', access_types, default='forbidden')
    card_html = db.Column(db.Text)
    provider_html = db.Column(db.Text)
    link_label = db.Column(db.Text)
    link_url = db.Column(db.Text)
    status_text = db.Column(db.Text)
    user_id = db.Column(db.ForeignKey('users.id'))
    intervention_id = db.Column(db.ForeignKey('interventions.id'))

    def as_json(self):
        d = {'user_id': self.user_id}
        for field in ('access', 'card_html', 'provider_html',
                      'link_label', 'link_url', 'status_text'):
            if getattr(self, field):
                d[field] = getattr(self, field)
        return d


STATIC_INTERVENTIONS = IterableUserDict({
    'assessment_engine': 'Assessment Engine',
    'care_plan': 'Care Plan',
    'community_of_wellness': 'Community of Wellness',
    'decision_support_p3p': 'Decision Support P3P',
    'decision_support_wisercare': 'Decision Support WiserCare',
    'self_management': 'Self Management',
    'sexual_recovery': 'Sexual Recovery',
    'social_support': 'Social Support Network',
    'default': 'OTHER: not yet officially supported'})


def add_static_interventions():
    """Seed database with default static interventions

    Idempotent - run anytime to push any new interventions into existing dbs

    """
    for name, description in STATIC_INTERVENTIONS.items():
        if not Intervention.query.filter_by(name=name).first():
            intervention = Intervention(
                name=name, description=description, card_html=description)
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
        value = self.__dict__[attr.lower()].__call__(self)
        return value


"""INTERVENTION behaves like a static accessor for all interventions.

Obtain intervention of choice by name in upper or lower case or by string:
    sr = INTERVENTION.SEXUAL_RECOVERY
    sr = INTERVENTION.sexual_recovery
    sr = getattr(INTERVENTION, 'sexual_recovery')

"""
INTERVENTION = _NamedInterventions(**STATIC_INTERVENTIONS)
