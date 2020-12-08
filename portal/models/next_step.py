"""Module for next_step logic"""
from flask import url_for
from werkzeug.exceptions import BadRequest

from .intervention import Intervention


class NextStep(object):
    """NextStep determination

    Extend the `next` logic encoded in a request path, to lookup the
    contextual meaning of the named step.

    """

    @staticmethod
    def validate(step):
        if hasattr(NextStep, step):
            return True
        raise BadRequest("{} not a valid next step".format(step))

    @staticmethod
    def home(user):
        return url_for('eproms.landing')

    @staticmethod
    def present_needed(user):
        return url_for(
            'assessment_engine_api.present_needed', subject_id=user.id)

    @staticmethod
    def decision_support(user):
        """Returns link to decision support applicable to user"""
        # Using same determination used for display of cards,
        # check each intervention with the `decision_support_*`
        # name pattern
        for option in Intervention.query.filter(
                Intervention.name.like("decision_support%")):
            if option.name == 'decision_support_unavailable':
                continue
            if option.quick_access_check(user=user):
                return option.link_url

        # Still here implies user doesn't meet requirements for any
        raise BadRequest("No decision support applicable to {}".format(user))
