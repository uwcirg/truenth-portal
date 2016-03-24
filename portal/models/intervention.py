"""Intervention Module"""
from flask import current_app
from UserDict import IterableUserDict
from sqlalchemy.dialects.postgresql import ENUM

from ..extensions import db, oauth
from .auth import Client


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

    def user_has_access(self, user):
        """Determine if given user has access to intervention

        If the intervention has `public_access` set, always returns
        true.  Otherwise, look for a UserIntervention row defining
        access for the given user on this intervention.

        @return True if user should be granted access to the intervention,
        False otherwise

        """
        if self.public_access:
            return True
        ui = UserIntervention.query.filter_by(
            user_id=user.id, intervention_id=self.id).first()
        if ui and ui.access != 'forbidden':
            return True
        return False

    def __str__(self):
        """print details needed in audit logs"""
        if self.name == INTERVENTION.DEFAULT:
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
    'care_plan': 'Care Plan',
    'community_of_wellness': 'Community of Wellness',
    'decision_support_p3p': 'Decision Support P3P',
    'decision_support_wisercare': 'Decision Support WiserCare',
    'self_management': 'Self Management',
    'sexual_recovery': 'Sexual Recovery',
    'social_support': 'Social Support Network',
    'default': 'OTHER: not yet officially supported'})


def enum(**items):
    """Convert dictionary to Enumeration for direct access"""
    return type('Enum', (), items)


INTERVENTION = enum(**{unicode(r).upper():r for r in STATIC_INTERVENTIONS})


def add_static_interventions():
    """Seed database with default static interventions

    Idempotent - run anytime to push any new interventions into existing dbs

    """
    config_map = {
        'care_plan': 'CARE_PLAN_INTERVENTION',
        'decision_support_p3p': 'DECIDING_INTERVENTION',
        'self_management': 'SELF_MANAGE_INTERVENTION',
    }
    for k, v in STATIC_INTERVENTIONS.items():
        if not Intervention.query.filter_by(name=k).first():
            intervention = Intervention(name=k, description=v,
                                        card_html=v)
            if k in config_map:
                intervention.card_url = current_app.config.get(config_map[k])
            db.session.add(intervention)


def named_interventions():
    """Return a named indexable structure for ease of use in the templates"""
    class NamedAttributes(object):
        pass

    parent = NamedAttributes()
    for intervention in Intervention.query.all():
        parent.__setattr__(intervention.name, intervention)
    return parent
