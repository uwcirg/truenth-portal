from collections import namedtuple

from ..models.auth import AuthProviderPersistable, Token
from ..models.client import Client
from ..models.intervention import Intervention
from ..models.relationship import RELATIONSHIP, Relationship
from ..models.role import ROLE, Role
from ..models.user import User, UserRelationship, UserRoles
from .model_persistence import ModelPersistence, require


# StagingExclusions capture details exclusive of a full db overwrite
# that are to be restored *after* db migration.  For example, when
# bringing the production db to staging, retain the staging
# config for interventions, application_developers and service users

def auth_providers_filter():
    """Return query restricted to application developer users"""
    return (
        AuthProviderPersistable.query.join(User).join(UserRoles).join(
            Role).filter(Role.name == ROLE.APPLICATION_DEVELOPER.value))


def client_users_filter():
    """Return query restricted to service users and those with client FKs"""
    return (
        User.query.join(Client).union(User.query.join(UserRoles).join(
            Role).filter(Role.name == ROLE.SERVICE.value)))


def relationship_filter():
    """Return query restricted to sponsor relationships (service users) """
    return UserRelationship.query.join(Relationship).filter(
        Relationship.name == RELATIONSHIP.SPONSOR.value)


def service_token_filter():
    """Return query restricted to tokens owned by service users"""
    return Token.query.join(User).join(UserRoles).join(Role).filter(
        Role.name == ROLE.SERVICE.value)


StagingExclusions = namedtuple(
    'StagingExclusions',
    ['cls', 'lookup_field', 'limit_to_attributes', 'filter_query'])
staging_exclusions = (
    StagingExclusions(Client, 'client_id', None, None),
    StagingExclusions(Intervention, 'name', ['link_url', 'client_id'], None),
    StagingExclusions(
        User, 'id', ['telecom', 'password'], client_users_filter),
    StagingExclusions(
        UserRelationship, ('user_id', 'other_user_id'), None,
        relationship_filter),
    StagingExclusions(
        AuthProviderPersistable, ('user_id', 'provider_id'), None,
        auth_providers_filter),
    StagingExclusions(Token, 'access_token', None, service_token_filter)
)


def preflight(target_dir):
    """Confirm database meets expectations prior to replacing data

    For exclusion persistence, rather than supporting the complexity of
    changing users, intervention owners, etc., confirm the local database
    contains any expectations before overwriting with persistence files

    :raises ValueError: if problems are discovered
    :returns: True if all clear

    """

    def persistence_by_type(cls):
        """Helper to pull details by type and return persistence instance"""
        ex_by_cls = [ex for ex in staging_exclusions if ex.cls == cls]
        if len(ex_by_cls) != 1:
            raise ValueError(
                "Expected exactly ONE but found {} staging_exclusions "
                "for {}".format(len(ex_by_cls), cls.__name__))

        for model in ex_by_cls:
            ex = ExclusionPersistence(
                model_class=model.cls, lookup_field=model.lookup_field,
                limit_to_attributes=model.limit_to_attributes,
                filter_query=model.filter_query,
                target_dir=target_dir)
            return ex

    # 1.) user_id associated with an intervention/client is the same
    client_persistence = persistence_by_type(Client)
    client_users = {}
    for c in client_persistence:
        client_users[c['client_id']] = c['user_id']

    intervention_persistence = persistence_by_type(Intervention)
    intervention_clients = {}
    for i in intervention_persistence:
        if 'client_id' in i:
            intervention_clients[i['name']] = i['client_id']

    for intervention_name, client_id in intervention_clients.items():
        if client_id not in client_users:
            raise ValueError(
                'no matching client found in persistence for {}'.format(
                    intervention_name))
        # look up local user_id associated with same intervention and
        # confirm match
        expected_user_id = Intervention.query.join(Client).filter(
            Intervention.client_id == Client.client_id).filter(
            Intervention.name == intervention_name).with_entities(
            Client.user_id).one()[0]
        if expected_user_id != client_users[client_id]:
            raise ValueError(
                "Mismatch - persistence files have {user_id} for "
                "{intervention_name}, whereas local db has "
                "{expected_user_id}".format(
                    user_id=client_users[client_id],
                    intervention_name=intervention_name,
                    expected_user_id=expected_user_id))

    # 2.) user_ids don't collide with anyone but a match
    user_persistence = persistence_by_type(User)
    for u in user_persistence:
        candidate = u['id']
        local = User.query.get(candidate)
        if not local:
            continue
        candidate_email = [
            t['value'] for t in u['telecom'] if t['system'] == 'email'][0]
        if candidate_email == local.email:
            continue
        raise ValueError(
            "persisted user<{}> will overwrite local <{}>; can't continue".format(
                candidate_email, local.email))
    return True


class ExclusionPersistence(ModelPersistence):
    """Specialized persistence for exclusive handling

    Manages exclusive details needed when replacing settings from one
    database to another.  For example, prior to pulling a fresh copy
    of production, one retains the configuration of the staging interventions
    such that they'll continue to function as previously configured for
    testing.  Otherwise, interventions would need to use production
    values or re-enter staging configuration values to test every time.

    """

    def __init__(
            self, model_class, limit_to_attributes, filter_query,
            target_dir=None, lookup_field='id', ):
        super(ExclusionPersistence, self).__init__(
            model_class=model_class,
            lookup_field=lookup_field,
            sequence_name=None,
            target_dir=target_dir)
        self.limit_to_attributes = limit_to_attributes
        self.filter_query = filter_query

    @property
    def query(self):
        """return ready query to obtain correct set of objects to persist"""
        if not self.filter_query:
            return super(ExclusionPersistence, self).query
        return self.filter_query()

    def require_lookup_field(self, obj, serial_form):
        """Include lookup_field when lacking"""
        results = dict(serial_form)

        if isinstance(self.lookup_field, tuple):
            for attr in self.lookup_field:
                require(obj, attr, serial_form)
            return serial_form

        # As the serialization method is often used for FHIR representation
        # and the object may not typically be handled by persistence, for
        # example with Users, force the lookup field into the serialization
        # form if missing.

        if self.lookup_field not in serial_form:
            results[self.lookup_field] = getattr(obj, self.lookup_field)
        return results

    def update(self, new_data):
        """Strip unwanted attributes before delegating to parent impl"""

        if self.limit_to_attributes is None:
            return super(ExclusionPersistence, self).update(new_data)

        keepers = set(self.limit_to_attributes)
        keepers.add(self.lookup_field)
        desired = {k: v for k, v in new_data.items() if k in keepers}
        return super(ExclusionPersistence, self).update(desired)
