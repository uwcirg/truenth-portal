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

from datetime import datetime
import json
import sys

from flask import current_app, url_for
from flask_babel import gettext as _
from sqlalchemy import UniqueConstraint, and_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from ..database import db
from ..date_tools import localize_datetime
from ..system_uri import DECISION_SUPPORT_GROUP, TRUENTH_CLINICAL_CODE_SYSTEM
from .clinical_constants import CC
from .codeable_concept import CodeableConcept
from .coding import Coding
from .identifier import Identifier
from .intervention import INTERVENTION, Intervention, UserIntervention
from .organization import Organization, OrganizationIdentifier, OrgTree
from .overall_status import OverallStatus
from .procedure_codes import known_treatment_started
from .role import Role

# ##
# # functions implementing the 'access_strategy' API
# ##

__log_strats = None


def _log(**kwargs):
    """Wrapper to log all the access lookup results within"""
    # get config value if haven't yet
    global __log_strats
    if __log_strats is None:
        __log_strats = current_app.config.get("LOG_DEBUG_STRATS", False)
    if __log_strats:
        msg = kwargs.get('message', '')  # optional
        current_app.logger.debug(
            "{func_name} returning {result} for {user} on intervention "
            "{intervention}".format(**kwargs) + msg)


def limit_by_clinic_w_id(
        identifier_value, identifier_system=DECISION_SUPPORT_GROUP,
        combinator='any', include_children=True):
    """Requires user is associated with {any,all} clinics with identifier

    :param identifier_value: value string for identifer associated with org(s)
    :param identifier_system: system string for identifier, defaults to
        DECISION_SUPPORT_GROUP
    :param combinator: determines if the user must be in 'any' (default) or
       'all' of the clinics in the given list.  NB combining 'all' with
       include_children=True would mean all orgs in the list AND all chidren of
       all orgs in list must be associated with the user for a true result.
    :param include_children: include children in the organization tree if
        set (default), otherwise, only include the organizations in the list

    """
    try:
        identifier = Identifier.query.filter_by(
            _value=identifier_value, system=identifier_system).one()
    except NoResultFound:
        raise ValueError(
            "strategy names non-existing Identifier({}, {})".format(
                identifier_value, identifier_system))

    orgs = Organization.query.join(OrganizationIdentifier).filter(and_(
        Organization.id == OrganizationIdentifier.organization_id,
        OrganizationIdentifier.identifier_id == identifier.id)).all()

    if include_children:
        ot = OrgTree()
        required = {o for og in orgs for o in ot.here_and_below_id(og.id)}
    else:
        required = set((o.id for o in orgs))
    if combinator not in ('any', 'all'):
        raise ValueError("unknown value {} for combinator, must be any or all")

    def user_registered_with_all_clinics(intervention, user):
        has = set((o.id for o in user.organizations))
        if required.intersection(has) == required:
            _log(result=True, func_name='limit_by_clinic_list', user=user,
                 intervention=intervention.name)
            return True

    def user_registered_with_any_clinics(intervention, user):
        has = set((o.id for o in user.organizations))
        if not required.isdisjoint(has):
            _log(result=True, func_name='limit_by_clinic_list', user=user,
                 intervention=intervention.name)
            return True

    return (
        user_registered_with_all_clinics if combinator == 'all'
        else user_registered_with_any_clinics)


def not_in_clinic_w_id(
        identifier_value, identifier_system=DECISION_SUPPORT_GROUP,
        include_children=True):
    """Requires user isn't associated with any clinic in the list

    :param identifier_value: value string for identifer associated with org(s)
    :param identifier_system: system string for identifier, defaults to
        DECISION_SUPPORT_GROUP
    :param include_children: include children in the organization tree if
        set (default), otherwise, only include the organizations directly
        associated with the identifier

    """
    try:
        identifier = Identifier.query.filter_by(
            _value=identifier_value, system=identifier_system).one()
    except NoResultFound:
        raise ValueError(
            "strategy names non-existing Identifier({}, {})".format(
                identifier_value, identifier_system))

    orgs = Organization.query.join(OrganizationIdentifier).filter(and_(
        Organization.id == OrganizationIdentifier.organization_id,
        OrganizationIdentifier.identifier_id == identifier.id)).all()

    if include_children:
        ot = OrgTree()
        dont_want = {o for og in orgs for o in ot.here_and_below_id(og.id)}
    else:
        dont_want = set((o.id for o in orgs))

    def user_not_registered_with_clinics(intervention, user):
        has = set((o.id for o in user.organizations))
        if has.isdisjoint(dont_want):
            _log(result=True, func_name='not_in_clinic_list', user=user,
                 intervention=intervention.name)
            return True

    return user_not_registered_with_clinics


def in_role_list(role_list):
    """Requires user is associated with any role in the list"""
    roles = []
    for role in role_list:
        try:
            role = Role.query.filter_by(
                name=role).one()
            roles.append(role)
        except NoResultFound:
            raise ValueError("role '{}' not found".format(role))
        except MultipleResultsFound:
            raise ValueError("more than one role named '{}'"
                             "found".format(role))
    required = set(roles)

    def user_has_given_role(intervention, user):
        has = set(user.roles)
        if has.intersection(required):
            _log(result=True, func_name='in_role_list', user=user,
                 intervention=intervention.name)
            return True

    return user_has_given_role


def not_in_role_list(role_list):
    """Requires user isn't associated with any role in the list"""
    roles = []
    for role in role_list:
        try:
            role = Role.query.filter_by(
                name=role).one()
            roles.append(role)
        except NoResultFound:
            raise ValueError("role '{}' not found".format(role))
        except MultipleResultsFound:
            raise ValueError("more than one role named '{}'"
                             "found".format(role))
    dont_want = set(roles)

    def user_not_given_role(intervention, user):
        has = set(user.roles)
        if has.isdisjoint(dont_want):
            _log(result=True, func_name='not_in_role_list', user=user,
                 intervention=intervention.name)
            return True

    return user_not_given_role


def allow_if_not_in_intervention(intervention_name):
    """Strategy API checks user does not belong to named intervention"""

    exclusive_intervention = getattr(INTERVENTION, intervention_name)

    def user_not_in_intervention(intervention, user):
        if not exclusive_intervention.quick_access_check(user):
            _log(result=True, func_name='user_not_in_intervention', user=user,
                 intervention=intervention.name)
            return True

    return user_not_in_intervention


def tx_begun(boolean_value):
    """Returns strategy function testing if user is known to have started Tx

    :param boolean_value: true for known treatment started (i.e. procedure
        indicating tx has begun), false to confirm a user doesn't have
        a procedure indicating tx has begun

    """
    if boolean_value == 'true':
        check_func = known_treatment_started
    elif boolean_value == 'false':
        def check_func(u):
            return not known_treatment_started(u)
    else:
        raise ValueError("expected 'true' or 'false' for boolean_value")

    def user_has_desired_tx(intervention, user):
        return check_func(user)

    return user_has_desired_tx


def observation_check(display, boolean_value, invert_logic=False):
    """Returns strategy function for a particular observation and logic value

    :param display: observation coding.display from
      TRUENTH_CLINICAL_CODE_SYSTEM
    :param boolean_value: ValueQuantity boolean true or false expected
    :param invert_logic: Effective binary ``not`` to apply to test.  If set,
      will return True only if given observation with boolean_value is NOT
      defined for user

    NB a history of observations is maintained, with the most recent taking
    precedence.

    """
    try:
        coding = Coding.query.filter_by(
            system=TRUENTH_CLINICAL_CODE_SYSTEM, display=display).one()
    except NoResultFound:
        raise ValueError("coding.display '{}' not found".format(display))
    try:
        cc = CodeableConcept.query.filter(
            CodeableConcept.codings.contains(coding)).one()
    except NoResultFound:
        raise ValueError("codeable_concept'{}' not found".format(coding))

    if boolean_value == 'true':
        vq = CC.TRUE_VALUE
    elif boolean_value == 'false':
        vq = CC.FALSE_VALUE
    else:
        raise ValueError("boolean_value must be 'true' or 'false'")

    def user_has_matching_observation(intervention, user):
        value, status = user.fetch_value_status_for_concept(
            codeable_concept=cc)
        if value == vq:
            _log(result=True, func_name='observation_check', user=user,
                 intervention=intervention.name,
                 message='{}:{}'.format(coding.display, vq.value))
            return True if not invert_logic else False
        return False if not invert_logic else True

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
        raise ValueError(
            "only supporting %d combined strategies", arbitrary_limit - 1)
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
        """Returns True if ALL of the combined strategies return True"""
        for strategy in strats:
            if not strategy(intervention, user):
                _log(
                    result=False, func_name='combine_strategies', user=user,
                    intervention=intervention.name)
                return
        # still here?  effective AND passed as all returned true
        _log(
            result=True, func_name='combine_strategies', user=user,
            intervention=intervention.name)
        return True

    def call_any_combined(intervention, user):
        """Returns True if ANY of the combined strategies return True"""
        for strategy in strats:
            if strategy(intervention, user):
                _log(
                    result=True, func_name='combine_strategies', user=user,
                    intervention=intervention.name)
                return True
        # still here?  effective ANY failed as none returned true
        _log(
            result=False, func_name='combine_strategies', user=user,
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
    intervention_id = db.Column(
        db.ForeignKey('interventions.id'), nullable=False)
    rank = db.Column(db.Integer)
    function_details = db.Column(JSONB, nullable=False)

    __table_args__ = (UniqueConstraint('intervention_id', 'rank',
                                       name='rank_per_intervention'),)

    def __str__(self):
        """Log friendly string format"""
        return (
            "AccessStrategy: {0.name} {0.description} {0.rank}"
            "{0.function_details}").format(self)

    @classmethod
    def from_json(cls, data):
        strat = cls()
        return strat.update_from_json(data)

    def update_from_json(self, data):
        try:
            self.name = data['name']
            if 'id' in data:
                self.id = data['id']
            if 'intervention_name' in data:
                intervention = Intervention.query.filter_by(
                    name=data['intervention_name']).first()
                if not intervention:
                    raise ValueError(
                        'Intervention not found {}.  (NB: new interventions '
                        'require `seed -i` to import)'.format(
                            data['intervention_name']))
                self.intervention_id = intervention.id
            if 'description' in data:
                self.description = data['description']
            if 'rank' in data:
                self.rank = data['rank']
            self.function_details = json.dumps(data['function_details'])

            # validate the given details by attempting to instantiate
            self.instantiate()
        except Exception as e:
            raise ValueError("AccessStrategy instantiation error: {}".format(
                e))
        return self

    def as_json(self):
        """Return self in JSON friendly dictionary"""
        d = {
            "name": self.name,
            "resourceType": 'AccessStrategy'
        }
        d["function_details"] = (
            json.loads(self.function_details) if self.function_details
            else None)
        d['intervention_name'] = (
            Intervention.query.get(self.intervention_id).name
            if self.intervention_id else None)
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
        # limit to this module
        func = getattr(sys.modules[__name__], func_name)
        kwargs = {}
        for argset in details['kwargs']:
            kwargs[argset['name']] = argset['value']
        return func(**kwargs)
