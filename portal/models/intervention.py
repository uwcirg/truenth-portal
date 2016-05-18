"""Intervention Module"""
from UserDict import IterableUserDict
from sqlalchemy.dialects.postgresql import ENUM

from ..extensions import db
from .lazy import query_by_name

class Intervention(db.Model):
    __tablename__ = 'interventions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    client_id = db.Column(db.ForeignKey('clients.client_id'))
    card_html = db.Column(db.Text)
    card_url = db.Column(db.Text)
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

    def user_has_access(self, user):
        """Determine if given user has access to intervention

        Somewhat complicated method, depending on intervention configuration.
        The following ordered steps are used to determine if a user
        should have access to an intervention.  The first 'true' found
        provides access, otherwise 'false' will be returned.

        1. check if the intervention has `public_access` set
        2. call each strategy_function in intervention.access_strategies
        3. check for a UserIntervention row defining access for the given
           user on this intervention.

        @return True if user should be granted access to the intervention,
        False otherwise

        """
        if self.public_access:
            return True

        for func in self.fetch_strategies():
            if func(intervention=self, user=user):
                return True

        ui = UserIntervention.query.filter_by(
            user_id=user.id, intervention_id=self.id).first()
        if ui and ui.access != 'forbidden':
            return True
        return False

    def __str__(self):
        """print details needed in audit logs"""
        if self.name == INTERVENTION.DEFAULT.name:
            return ""
        return "Intervention: {0}, public_access: {1}, "\
                "card_url: {2} card_html: {3}".format(
                self.description, self.public_access,
                self.card_url, self.card_html)


access_types = ENUM('forbidden', 'granted', name='access',
                    create_type=False)


class UserIntervention(db.Model):
    __tablename__ = 'user_interventions'
    id = db.Column(db.Integer, primary_key=True)
    access = db.Column('access', access_types, default='forbidden')
    card_html = db.Column(db.Text)
    user_id = db.Column(db.ForeignKey('users.id'))
    intervention_id = db.Column(db.ForeignKey('interventions.id'))


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
