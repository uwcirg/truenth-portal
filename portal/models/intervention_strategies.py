"""Module for intervention access strategy functions

Determining whether or not to provide access to a given intervention
for a user is occasionally tricky business.  By way of the access_strategies
property on all interventions, one can add additional criteria by defining a
function here (or elsewhere) and adding it to the desired intervention.

function signature: takes named parameters (intervention, user) and returns
a boolean - True grants access (and short circuits further access tests),
False does not.

NB - several functions are closures returning access_strategy functions with
the parameters given to the closures.

"""
from flask import current_app
import json
from sqlalchemy.dialects.postgresql import JSONB
import sys

from ..extensions import db
from .fhir import CC
from .organization import Organization
from .intervention import INTERVENTION


###
## functions implementing the 'access_strategy' API
#

def _log(**kwargs):
    """Wrapper to log all the access lookup results within"""
    current_app.logger.debug(
        "{func_name} returning {result} for {user} on intervention "\
        "{intervention}".format(**kwargs))

def limit_by_clinic(organization_name):
    """Returns function implenting strategy API checking for named org"""
    organization = Organization.query.filter_by(name=organization_name).one()

    def user_registered_with_clinic(intervention, user):
        if organization in user.organizations:
            _log(result=True, func_name='limit_by_clinic', user=user,
                 intervention=intervention.name)
            return True
    return user_registered_with_clinic

def allow_if_not_in_intervention(intervention_name):
    """Returns function implementing strategy API checking that user does not belong to named intervention"""

    exclusive_intervention = getattr(INTERVENTION, intervention_name)

    def user_not_in_intervention(intervention, user):
        if not exclusive_intervention.user_has_access(user):
            _log(result=True, func_name='user_not_in_intervention', user=user,
                 intervention=intervention.name)
            return True
    return user_not_in_intervention

def diagnosis_w_o_tx():
    """Returns function implementing strategy API checks for PCa and no TX"""

    def diag_no_tx(intervention, user):
        """Returns true if user has a PCa diagnosis and no TX"""
        pca = [o for o in user.observations if o.codeable_concept_id ==
               CC.PCaDIAG.id]
        tx = [o for o in user.observations if o.codeable_concept_id ==
              CC.TX.id]
        has_pca = pca and pca[0].value_quantity == CC.TRUE_VALUE
        in_tx = tx and tx[0].value_quantity == CC.TRUE_VALUE

        if has_pca and not in_tx:
            _log(result=True, func_name='diag_no_tx', user=user,
                 intervention=intervention.name)
            return True
    return diag_no_tx


class AccessStrategy(db.Model):
    """ORM to persist access strategies on an intervention

    The function_details field contains JSON defining which strategy to
    use and how it should be instantiated by one of the closures implementing
    the access_strategy interface.  Said closures must be defined in this
    module (a security measure to keep unsanitized code out).

    """
    __tablename__ = 'access_strategies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    intervention_id = db.Column(db.ForeignKey('interventions.id'))
    rank = db.Column(db.Integer)
    function_details = db.Column(JSONB, nullable=False)

    def __str__(self):
        """Log friendly string format"""
        return "AccessStrategy: {0.name} {0.description} {0.rank}"\
            "{0.function_details}".format(self)

    @classmethod
    def from_json(cls, data):
        obj = cls()
        try:
            obj.name = data['name']
            if 'description' in data:
                obj.description = data['description']
            if 'rank' in data:
                obj.rank = data['rank']
            obj.function_details = json.dumps(data['function_details'])

            # validate the given details by attempting to instantiate
            obj.instantiate()
        except Exception, e:
            raise ValueError("well defined AccessStrategy includes at "
                             "a minimum 'name' and 'function_details': {}".\
                            format(e))

        return obj

    def as_json(self):
        """Return self in JSON friendly dictionary"""
        d = {"name": self.name,
             "function_details": json.loads(self.function_details)}
        if self.rank:
            d['rank'] = self.rank
        if self.description:
            d['description'] = self.description
        return d

    def instantiate(self):
        """Bring the serialized access strategy function to life

        Using the JSON in self.function_details, instantiate the
        function and return it ready to use.

        """
        details = json.loads(self.function_details)
        if 'function' not in details:
            raise ValueError("'function' not found in function_details")
        if 'kwargs' not in details:
            raise ValueError("'kwargs' not found in function_details")
        func_name = details['function']
        func = getattr(sys.modules[__name__], func_name) # limit to this module
        kwargs = {}
        for argset in details['kwargs']:
            kwargs[argset['name']] = argset['value']
        return func(**kwargs)

