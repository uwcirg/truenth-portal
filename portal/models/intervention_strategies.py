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
from sqlalchemy import and_, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
import sys

from ..extensions import db
from .fhir import CC, Coding, CodeableConcept
from .organization import Organization
from .intervention import Intervention, INTERVENTION, UserIntervention
from ..system_uri import TRUENTH_CLINICAL_CODE_SYSTEM


###
## functions implementing the 'access_strategy' API
#

def _log(**kwargs):
    """Wrapper to log all the access lookup results within"""
    msg = kwargs.get('message', '')  # optional
    current_app.logger.debug(
        "{func_name} returning {result} for {user} on intervention "\
        "{intervention}".format(**kwargs) + msg)

def limit_by_clinic_list(org_list, combinator='all'):
    """Requires user is associated with {any,all} clinics in the list

    Value of combinator determines if the user must be in 'any' or 'all' of the
    clinics in the given list.

    """
    orgs = []
    for org in org_list:
        try:
            organization = Organization.query.filter_by(
                name=org).one()
            orgs.append(organization)
        except NoResultFound:
            raise ValueError("organization '{}' not found".format(org))
        except MultipleResultsFound:
            raise ValueError("multiple matches for org name {}".format(org))
    required = set(orgs)
    if combinator not in ('any', 'all'):
        raise ValueError("unknown value {} for combinator, must be any or all")

    def user_registered_with_all_clinics(intervention, user):
        has = set(user.organizations)
        if required.intersection(has) == required:
            _log(result=True, func_name='limit_by_clinic_list', user=user,
                 intervention=intervention.name)
            return True

    def user_registered_with_any_clinics(intervention, user):
        has = set(user.organizations)
        if not required.isdisjoint(has):
            _log(result=True, func_name='limit_by_clinic_list', user=user,
                 intervention=intervention.name)
            return True

    return user_registered_with_all_clinics if combinator == 'all' else\
        user_registered_with_any_clinics

def not_in_clinic_list(org_list):
    """Requires user isn't associated with any clinic in the list"""
    orgs = []
    for org in org_list:
        try:
            organization = Organization.query.filter_by(
                name=org).one()
            orgs.append(organization)
        except NoResultFound:
            raise ValueError("organization '{}' not found".format(org))
        except MultipleResultsFound:
            raise ValueError("more than one organization named '{}'"
                             "found".format(org))
    dont_want = set(orgs)

    def user_not_registered_with_clinics(intervention, user):
        has = set(user.organizations)
        if has.isdisjoint(dont_want):
            _log(result=True, func_name='not_in_clinic_list', user=user,
                 intervention=intervention.name)
            return True

    return user_not_registered_with_clinics

def allow_if_not_in_intervention(intervention_name):
    """Returns function implementing strategy API checking that user does not belong to named intervention"""

    exclusive_intervention = getattr(INTERVENTION, intervention_name)

    def user_not_in_intervention(intervention, user):
        if not exclusive_intervention.display_for_user(user).access:
            _log(result=True, func_name='user_not_in_intervention', user=user,
                 intervention=intervention.name)
            return True

    return user_not_in_intervention


def update_link_url(intervention_name, link_url):
    """Intervention may need special link per user - set to given for user"""

    intervention = getattr(INTERVENTION, intervention_name)

    def update_user_intervention(intervention, user):
        # NB - this is by design, a method with side effects
        # if the user_intevention isn't present, or doesn't include a
        # matching link_url - one will be created or updated.
        ui = UserIntervention.query.filter(and_(
            UserIntervention.user_id == user.id,
            UserIntervention.intervention_id == intervention.id)).first()
        if not ui:
            db.session.add(UserIntervention(user_id = user.id,
                                           intervention_id = intervention.id,
                                           link_url = link_url))
            db.session.commit()
        else:
            if ui.link_url != link_url:
                ui.link_url = link_url
                db.session.commit()

        # Really this function just exists for the side effects, don't
        # prevent access
        return True

    return update_user_intervention


def observation_check(display, boolean_value):
    """Returns strategy function for a particular observation and logic value

    :param display: observation coding.display from TRUENTH_CLINICAL_CODE_SYSTEM
    :param boolean_value: ValueQuantity boolean true or false expected

    """
    try:
        coding = Coding.query.filter_by(
            system=TRUENTH_CLINICAL_CODE_SYSTEM, display=display).one()
    except NoResultFound:
        raise ValueError("coding.display '{}' not found".format(display))
    try:
        cc_id = CodeableConcept.query.filter(
            CodeableConcept.codings.contains(coding)).one().id
    except NoResultFound:
        raise ValueError("codeable_concept'{}' not found".format(coding))

    if boolean_value == 'true':
        vq = CC.TRUE_VALUE
    elif boolean_value == 'false':
        vq = CC.FALSE_VALUE
    else:
        raise ValueError("boolean_value must be 'true' or 'false'")

    def user_has_matching_observation(intervention, user):
        obs = [o for o in user.observations if o.codeable_concept_id == cc_id]
        if obs and obs[0].value_quantity == vq:
            _log(result=True, func_name='diag_no_tx', user=user,
                 intervention=intervention.name,
                 message='{}:{}'.format(coding.display, vq.value))
            return True

    return user_has_matching_observation


def combine_strategies(**kwargs):
    """Make multiple strategies into a single statement

    The nature of the access lookup returns True for the first
    success in the list of strategies for an intervention.  Use
    this method to chain multiple strategies together into a logical **and**
    fashion rather than the built in locical **or**.

    NB - kwargs must have keys such as 'strategy_n', 'strategy_n_kwargs'
    for every 'n' strategies being combined, starting at 1.  Set arbitrary
    limit of 6 strategies for time being.

    Nested strategies may actually want a logical 'OR'.  Optional kwarg
    `combinator` takes values {'any', 'all'} - default 'all' means all
    strategies must evaluate true.  'any' means just one must eval true for a
    positive result.

    """
    strats = []
    arbitrary_limit = 7
    if 'strategy_{}'.format(arbitrary_limit) in kwargs:
        raise ValueError("only supporting %d combined strategies",
                         arbitrary_limit-1)
    for i in range(1, arbitrary_limit):
        if 'strategy_{}'.format(i) not in kwargs:
            break

        func_name = kwargs['strategy_{}'.format(i)]

        func_kwargs = {}
        for argset in kwargs['strategy_{}_kwargs'.format(i)]:
            func_kwargs[argset['name']] = argset['value']

        func = getattr(sys.modules[__name__], func_name)
        strats.append(func(**func_kwargs))

    def call_all_combined(intervention, user):
        "Returns True if ALL of the combined strategies return True"
        for strategy in strats:
            if not strategy(intervention, user):
                _log(result=False, func_name='combine_strategies', user=user,
                    intervention=intervention.name)
                return
        # still here?  effective AND passed as all returned true
        _log(result=True, func_name='combine_strategies', user=user,
            intervention=intervention.name)
        return True

    def call_any_combined(intervention, user):
        "Returns True if ANY of the combined strategies return True"
        for strategy in strats:
            if strategy(intervention, user):
                _log(result=True, func_name='combine_strategies', user=user,
                    intervention=intervention.name)
                return True
        # still here?  effective ANY failed as none returned true
        _log(result=False, func_name='combine_strategies', user=user,
            intervention=intervention.name)
        return

    combinator = kwargs.get('combinator', 'all')
    if combinator == 'any':
        return call_any_combined
    elif combinator == 'all':
        return call_all_combined
    else:
        raise ValueError("unrecognized value {} for `combinator`, "
                         "limited to {'any', 'all'}").format(combinator)


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

    __table_args__ = (UniqueConstraint('intervention_id', 'rank',
                                       name='rank_per_intervention'),)

    def __str__(self):
        """Log friendly string format"""
        return "AccessStrategy: {0.name} {0.description} {0.rank}"\
            "{0.function_details}".format(self)

    @classmethod
    def from_json(cls, data):
        obj = cls()
        try:
            obj.name = data['name']
            if 'id' in data:
                obj.id = data['id']
            if 'intervention_name' in data:
                obj.intervention_id = Intervention.query.filter_by(
                    name=data['intervention_name']).one().id
            if 'description' in data:
                obj.description = data['description']
            if 'rank' in data:
                obj.rank = data['rank']
            obj.function_details = json.dumps(data['function_details'])

            # validate the given details by attempting to instantiate
            obj.instantiate()
        except Exception, e:
            raise ValueError("AccessStrategy instantiation error: {}".format(
                e))
        return obj

    def as_json(self):
        """Return self in JSON friendly dictionary"""
        d = {"name": self.name,
             "function_details": json.loads(self.function_details),
             "resourceType": 'AccessStrategy'
            }
        d['intervention_name'] = Intervention.query.get(
            self.intervention_id).name
        if self.id:
            d['id'] = self.id
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

