"""User API view functions"""
from flask import abort, Blueprint, jsonify, url_for
from flask import request
from flask_user import roles_required

from ..audit import auditable_event
from ..extensions import db, oauth, user_manager
from ..models.audit import Audit
from ..models.group import Group
from ..models.organization import Organization
from ..models.role import ROLE, Role
from ..models.relationship import Relationship
from ..models.user import current_user, get_user
from ..models.user import User, UserRelationship
from ..models.user_consent import UserConsent

user_api = Blueprint('user_api', __name__, url_prefix='/api')

@user_api.route('/me')
@oauth.require_oauth()
def me():
    """Access basics for current user

    returns authenticated user's id, username and email in JSON
    ---
    tags:
      - User
    operationId: me
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: user
          required:
            - id
            - username
            - email
          properties:
            id:
              type: integer
              format: int64
              description: TrueNTH ID for user
            username:
              type: string
              description: User's username - which will always match the email
            email:
              type: string
              description: User's preferred email address, same as username
      401:
        description: if missing valid OAuth token

    """
    user = current_user()
    return jsonify(id=user.id, username=user.username,
                   email=user.email)


@user_api.route('/account', methods=('POST',))
@oauth.require_oauth()
@roles_required([ROLE.APPLICATION_DEVELOPER, ROLE.ADMIN, ROLE.SERVICE,
                ROLE.PROVIDER])
def account():
    """Create a user account

    Use cases:
    Interventions call this, get a truenth ID back, and subsequently call:
    1. PUT /api/demographics/{id}, with known details for the new user
    2. PUT /api/user/{id}/roles to grant the user role(s)
    3. PUT /api/intervention/{name} grants the user access to the intervention.
    ---
    tags:
      - User
    operationId: createAccount
    parameters:
      - in: body
        name: body
        schema:
          id: account_args
          properties:
            organizations:
              type: array
              items:
                type: object
                required:
                  - organization_id
                properties:
                  organization_id:
                      type: string
                      description:
                        Optional organization identifier defining the
                        organization the new user will belong to.
    produces:
      - application/json
    responses:
      200:
        description:
            "Returns {user_id: id}"
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id
    """
    user = User()
    db.session.add(user)
    db.session.commit()
    auditable_event("new account {} generated".format(user.id),
                    user_id=current_user().id)
    if request.json and 'organizations' in request.json:
        # confirm org exists
        for org in request.json['organizations']:
            org_id = org['organization_id']
            org = Organization.query.get(org_id)
            if not org:
                abort(400, "Organization {} not found".format(org_id))
            # add org to users account
            user.organizations.append(org)
        db.session.commit()
        auditable_event("added {} to {}".format(org, user),
                        user_id=current_user().id)
    return jsonify(user_id=user.id)


@user_api.route('/user/<int:user_id>/access_url')
@oauth.require_oauth()
@roles_required([ROLE.APPLICATION_DEVELOPER, ROLE.ADMIN, ROLE.SERVICE,
                ROLE.PROVIDER])
def access_url(user_id):
    """Returns simple JSON with one-time, unique access URL for given user

    Generates a single use access token for the given user as a
    one click, weak authentication access to the system.

    NB - user must be a member of the WRITE_ONLY role, and not a member
    of privileged roles, as a safeguard from abuse.

    ---
    tags:
      - User
    operationId: access_url
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID to grant access via unique URL
        required: true
        type: integer
        format: int64
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: response
          required:
            - access_url
          properties:
            access_url:
              type: string
              description: The unique URL providing one time access
      400:
        description:
          if the user has too many privileges for weak authentication
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id
      404:
        description: if the user isn't found

    """
    user = get_user(user_id)
    if not user:
        abort(404, "User {} not found".format(user_id))
    current_user().check_role(permission='edit', other_id=user_id)
    not_allowed = set([ROLE.ADMIN, ROLE.APPLICATION_DEVELOPER, ROLE.SERVICE,
                      ROLE.PROVIDER])
    has = set([role.name for role in user.roles])
    if not has.isdisjoint(not_allowed):
        abort(400, "Access URL not provided for privileged accounts")

    #if not ROLE.WRITE_ONLY in has:
        # KEEP this restriction.  Weak authentication (which the
        # returned URL provides) should only be available for WRITE_ONLY users
    #    abort(400, "Account {} lacks WRITE_ONLY role".format(user_id))

    # generate an access token
    token = user_manager.token_manager.generate_token(user_id)
    access_url = url_for(
        'portal.access_via_token', token=token, _external=True)
    auditable_event("generated access token for user {}".format(user_id),
                    user_id=current_user().id)
    return jsonify(access_url=access_url)


@user_api.route('/user/<int:user_id>/consent')
@oauth.require_oauth()
def user_consents(user_id):
    """Returns simple JSON listing user's valid consent agreements

    Returns the list of consent agreements between the requested user
    and the respective organizations.

    NB does not include expired or deleted consents.

    ---
    tags:
      - User
      - Consent
      - Organization
    operationId: user_consents
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
    produces:
      - application/json
    responses:
      200:
        description:
          Returns the list of consent agreements for the requested user.
        schema:
          id: consents
          properties:
            consent_agreements:
              type: array
              items:
                type: object
                required:
                  - user_id
                  - organization_id
                  - signed
                  - expires
                  - agreement_url
                properties:
                  user_id:
                    type: string
                    description:
                      User identifier defining with whom the consent agreement
                      applies
                  organization_id:
                    type: string
                    description:
                      Organization identifier defining with whom the consent
                      agreement applies
                  signed:
                    type: string
                    format: date-time
                    description:
                      Original UTC date-time from the moment the agreement was
                      signed or put in place by some other workflow
                  expires:
                    type: string
                    format: date-time
                    description:
                      UTC date-time for when the agreement expires, typically 5
                      years from the original signing date
                  agreement_url:
                    type: string
                    description: URL pointing to agreement text
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='view', other_id=user_id)
        user = get_user(user_id)
    if not user:
        abort(404, "User {} not found".format(user_id))

    return jsonify(consent_agreements=[c.as_json() for c in
                                       user.valid_consents])


@user_api.route('/user/<int:user_id>/consent', methods=('POST',))
@oauth.require_oauth()
def set_user_consents(user_id):
    """Add a consent agreement for the user with named organization

    Used to add a consent agreements between a user and an organization.
    Assumed to have just been agreed to.  Include 'expires' if
    necessary, defaults to now and five years from now (both in UTC).

    ---
    tags:
      - User
      - Consent
      - Organization
    operationId: post_user_consent
    produces:
      - application/json
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: consent_agreement
          required:
            - organization_id
            - agreement_url
          properties:
            organization_id:
              type: integer
              format: int64
              description:
                Organization identifier defining with whom the consent
                agreement applies
            expires:
              type: string
              format: date-time
              description:
                UTC date-time for when the agreement expires, defaults to
                utcnow plus 5 years
            agreement_url:
              type: string
              description: URL pointing to agreement text
    responses:
      200:
        description: successful operation
        schema:
          id: response
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      400:
        description: if the request incudes invalid data
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to edit requested user_id
      404:
        description: if user_id doesn't exist

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='edit', other_id=user_id)
        user = get_user(user_id)
    if not user:
        abort(404, "user_id {} not found".format(user_id))
    request.json['user_id'] = user_id
    try:
        consent = UserConsent.from_json(request.json)
        if request.json.get('expires'):
            consent.expires = request.json.get('expires')
    except ValueError as e:
        abort(400, str(e))

    audit = Audit(user_id=current_user().id,
                  comment="Adding consent agreement")
    consent.audit = audit
    db.session.add(consent)
    db.session.commit()

    return jsonify(message="ok")


@user_api.route('/user/<int:user_id>/consent', methods=('DELETE',))
@oauth.require_oauth()
def delete_user_consents(user_id):
    """Delete a consent agreement between the user and the named organization

    Used to delete consent agreements between a user and an organization.

    ---
    tags:
      - User
      - Consent
      - Organization
    operationId: delete_user_consent
    produces:
      - application/json
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: consent_agreement
          required:
            - organization_id
          properties:
            organization_id:
              type: integer
              format: int64
              description:
                Organization identifier defining with whom the consent
                agreement applies
    responses:
      200:
        description: successful operation
        schema:
          id: response
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      400:
        description: if the request incudes invalid data
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to edit requested user_id
      404:
        description: if user_id doesn't exist

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='edit', other_id=user_id)
        user = get_user(user_id)
    if not user:
        abort(404, "user_id {} not found".format(user_id))
    remove_uc = None
    try:
        id_to_delete = int(request.json['organization_id'])
    except ValueError:
        abort(400, "requires integer value for `organization_id`")
    for uc in user.valid_consents:
        if uc.organization.id == id_to_delete:
            remove_uc = uc
            break
    if not remove_uc:
        abort(404, "matching user consent not found")

    remove_uc.deleted = Audit(
        user_id=current_user().id, comment="Deleted consent agreement")
    db.session.commit()

    return jsonify(message="ok")


@user_api.route('/user/<int:user_id>/groups')
@oauth.require_oauth()
def user_groups(user_id):
    """Returns simple JSON defining user's groups

    Returns the list of groups the requested user belongs to.
    ---
    tags:
      - User
      - Group
    operationId: user_groups
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
    produces:
      - application/json
    responses:
      200:
        description:
          Returns the list of groups the requested user belongs to.
        schema:
          id: groups
          required:
            - name
            - description
          properties:
            name:
              type: string
              description:
                Group name, always a lower case string with no white space.
            description:
              type: string
              description: Plain text describing the group.
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='view', other_id=user_id)
        user = get_user(user_id)
    if not user:
        abort(404, "User {} not found".format(user_id))

    return jsonify(groups=[g.as_json() for g in user.groups])


@user_api.route('/user/<int:user_id>/groups', methods=('PUT',))
@oauth.require_oauth()
def set_user_groups(user_id):
    """Set groups for user, returns simple JSON defining user groups

    Used to set group assignments for a user.  Include all groups
    the user should be a member of.  If user previously belonged to
    groups not included, the missing groups will be deleted from the user.

    Only the 'name' field of the groups is referenced.  Must match
    current groups in the system.

    Returns a list of all groups user belongs to after change.
    ---
    tags:
      - User
      - Group
    operationId: set_user_groups
    produces:
      - application/json
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: nested_groups
          properties:
            groups:
              type: array
              items:
                type: object
                required:
                  - name
                properties:
                  name:
                    type: string
                    description:
                      The string defining the name of each group the user should
                      belong to.  Must exist as an available group in the system.
    responses:
      200:
        description:
          Returns a list of all groups user belongs to after change.
        schema:
          id: user_groups
          required:
            - name
            - description
          properties:
            name:
              type: string
              description:
                Group name, always a lower case string with no white space.
            description:
              type: string
              description: Plain text describing the group.
      400:
        description: if the request incudes an unknown group.
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to edit requested user_id
      404:
        description: if user_id doesn't exist

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='edit', other_id=user_id)
        user = get_user(user_id)
    if not user:
        abort(404, "user_id {} not found".format(user_id))

    if not request.json or 'groups' not in request.json:
        abort(400, "Requires 'groups' list")

    remove_if_not_requested = {group.id: group for group in user.groups}
    requested_groups = [r['name'] for r in request.json['groups']]
    matching_groups = Group.query.filter(Group.name.in_(requested_groups)).all()
    if len(matching_groups) != len(requested_groups):
        abort(400, "One or more groups requested not available")
    # Add any requested not already set on user
    for requested_group in matching_groups:
        if requested_group not in user.groups:
            user.groups.append(requested_group)
            auditable_event("added {} to user {}".format(
                requested_group, user.id), user_id=current_user().id)
        else:
            remove_if_not_requested.pop(requested_group.id)

    for stale_group in remove_if_not_requested.values():
        user.groups.remove(stale_group)
        auditable_event("deleted {} from user {}".format(
            stale_group, user.id), user_id=current_user().id)

    if user not in db.session:
        db.session.add(user)
    db.session.commit()

    # Return user's updated group list
    return jsonify(groups=[g.as_json() for g in user.groups])


@user_api.route('/relationships')
@oauth.require_oauth()
def system_relationships():
    """Returns simple JSON defining all system relationships

    Returns a list of all known relationships.
    ---
    tags:
      - User
      - Relationship
    operationId: system_relationships
    produces:
      - application/json
    responses:
      200:
        description: Returns a list of all known relationships.
        schema:
          id: relationships
          required:
            - name
            - description
          properties:
            name:
              type: string
              description:
                relationship name, a lower case string with no white space.
            description:
              type: string
              description: Plain text describing the relationship.
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view system relationships

    """
    results = [{'name': r.name, 'description': r.description}
               for r in Relationship.query.all()]
    return jsonify(relationships=results)


@user_api.route('/user/<int:user_id>/relationships')
@oauth.require_oauth()
def relationships(user_id):
    """Returns simple JSON defining user relationships

    Relationships may exist between user accounts.  A user may have
    any number of relationships.  The relationship
    is a one-way definition defined to extend permissions to appropriate
    users, such as intimate partners or service account sponsors.

    The JSON returned includes all relationships for the given user both
    as subject and as part of the relationship predicate.
    ---
    tags:
      - User
      - Relationship
    operationId: getrelationships
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
    produces:
      - application/json
    responses:
      200:
        description:
          Returns the list of relationships the requested user belongs to.
        schema:
          id: user_relationships
          required:
            - user
            - has the relationship
            - with
          properties:
            user:
              type: integer
              format: int64
              description: id of user acting as subject
            has the relationship:
              type: string
              description:
                The string defining the name of each relationship the user
                should belong to.  Must exist as an available relationship
                in the system.
            with:
              type: integer
              format: int64
              description: id of user acting as part of predicate
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='view', other_id=user_id)
        user = get_user(user_id)
    results = []
    for r in user.relationships:
        results.append({'user': r.user_id,
                        'has the relationship': r.relationship.name,
                        'with': r.other_user_id})
    # add in any relationships where the user is on the predicate side
    predicates = UserRelationship.query.filter_by(other_user_id=user_id)
    for r in predicates:
        results.append({'user': r.user_id,
                        'has the relationship': r.relationship.name,
                        'with': r.other_user_id})
    return jsonify(relationships=results)


@user_api.route('/user/<int:user_id>/relationships', methods=('PUT',))
@oauth.require_oauth()
def set_relationships(user_id):
    """Set relationships for user, returns JSON defining user relationships

    Used to set relationship assignments for a user, both in a subject
    and predicate role.  The provided list of relationships will be definitive,
    resulting in deletion of previously existing relationships omitted from
    the given list (again where user_id is acting as the relationship
    subject or part of predicate).

    Returns a list of all relationships user belongs to after change.
    ---
    tags:
      - User
      - Relationship
    operationId: setrelationships
    produces:
      - application/json
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: user_relationships
          required:
            - user
            - has the relationship
            - with
          properties:
            user:
              type: integer
              format: int64
              description: id of user acting as subject
            has the relationship:
              type: string
              description:
                The string defining the name of each relationship the user
                should belong to.  Must exist as an available relationship
                in the system.
            with:
              type: integer
              format: int64
              description: id of user acting as part of predicate
    responses:
      200:
        description:
          Returns a list of all relationships user belongs to after change.
        schema:
          id: user_relationships
          required:
            - user
            - has the relationship
            - with
          properties:
            user:
              type: integer
              format: int64
              description: id of user acting as subject
            has the relationship:
              type: string
              description:
                The string defining the name of each relationship the user
                should belong to.  Must exist as an available relationship
                in the system.
            with:
              type: integer
              format: int64
              description: id of user acting as part of predicate
      400:
        description: if the request incudes an unknown relationship.
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='edit', other_id=user_id)
        user = get_user(user_id)

    if not request.json or 'relationships' not in request.json:
        abort(400, "Requires relationship list in JSON")
    # First confirm all the data is valid and the user has permission
    system_relationships = [r.name for r in Relationship.query]
    for r in request.json['relationships']:
        if not r['has the relationship'] in system_relationships:
            abort(404, "Unknown relationship '{}' can't be added".format(
                r['has the relationship']))
        if r['user'] == r['with']:
            abort(400, "Relationship must be between two different users")
        if not user_id in (r['user'], r['with']):
            abort(401, "Path user must be part of relationship")

    subjects = [ur for ur in user.relationships]
    predicates = [ur for ur in
                  UserRelationship.query.filter_by(other_user_id=user.id)]
    remove_if_not_requested = {ur.id: ur for ur in subjects + predicates}

    # Add any requested that don't exist, track what isn't mentioned for
    # deltion.
    audit_adds = []  # preserve till post commit
    audit_dels = []  # preserve till post commit
    for r in request.json['relationships']:
        rel_id = Relationship.query.with_entities(
            Relationship.id).filter_by(name=r['has the relationship']).first()
        kwargs = {'user_id': r['user'],
                  'relationship_id': rel_id[0],
                  'other_user_id': r['with']}
        existing = UserRelationship.query.filter_by(**kwargs).first()
        if not existing:
            user_relationship = UserRelationship(**kwargs)
            db.session.add(user_relationship)
            audit_adds.append(user_relationship)
        else:
            remove_if_not_requested.pop(existing.id)

    for ur in remove_if_not_requested.values():
        audit_dels.append(''.format(ur))
        db.session.delete(ur)

    db.session.commit()
    for ad in audit_adds:
        auditable_event("added {}".format(ad),
                        user_id=current_user().id)
    for ad in audit_dels:
        auditable_event("deleted {}".format(ad),
                        user_id=current_user().id)
    # Return user's updated relationship list
    return relationships(user.id)


@user_api.route('/roles')
@oauth.require_oauth()
def system_roles():
    """Returns simple JSON defining all system roles

    Returns a list of all known roles.  Users belong to one or more
    roles used to control authorization.
    ---
    tags:
      - User
      - Role
    operationId: system_roles
    produces:
      - application/json
    responses:
      200:
        description:
          Returns a list of all known roles.  Users belong to one or more
          roles used to control authorization.
        schema:
          id: nested_roles
          properties:
            roles:
              type: array
              items:
                type: object
                required:
                  - name
                  - description
                properties:
                  name:
                    type: string
                    description:
                      Role name, always a lower case string with no white space.
                  description:
                    type: string
                    description: Plain text describing the role.
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view roles

    """
    results = [{'name': r.name, 'description': r.description}
            for r in Role.query.all()]
    return jsonify(roles=results)


@user_api.route('/user/<int:user_id>/roles')
@oauth.require_oauth()
def roles(user_id):
    """Returns simple JSON defining user roles

    Returns the list of roles the requested user belongs to.
    ---
    tags:
      - User
      - Role
    operationId: getRoles
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
    produces:
      - application/json
    responses:
      200:
        description:
          Returns the list of roles the requested user belongs to.
        schema:
          id: nested_roles
          properties:
            roles:
              type: array
              items:
                type: object
                required:
                  - name
                  - description
                properties:
                  name:
                    type: string
                    description:
                      Role name, always a lower case string with no white space.
                  description:
                    type: string
                    description: Plain text describing the role.
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='view', other_id=user_id)
        user = get_user(user_id)
    results = [{'name': r.name, 'description': r.description}
            for r in user.roles]
    return jsonify(roles=results)


@user_api.route('/user/<int:user_id>/roles', methods=('PUT',))
@oauth.require_oauth()
def set_roles(user_id):
    """Set roles for user, returns simple JSON defining user roles

    Used to set role assignments for a user.  Include all roles
    the user should be a member of.  If user previously belonged to
    roles not included, the missing roles will be deleted from the user.

    Only the 'name' field of the roles is referenced.  Must match
    current roles in the system.

    Returns a list of all roles user belongs to after change.
    ---
    tags:
      - User
      - Role
    operationId: setRoles
    produces:
      - application/json
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: nested_roles
          properties:
            roles:
              type: array
              items:
                type: object
                required:
                  - name
                properties:
                  name:
                    type: string
                    description:
                      The string defining the name of each role the user should
                      belong to.  Must exist as an available role in the system.
    responses:
      200:
        description:
          Returns a list of all roles user belongs to after change.
        schema:
          id: nested_roles
          properties:
            roles:
              type: array
              items:
                type: object
                required:
                  - name
                  - description
                properties:
                  name:
                    type: string
                    description:
                      Role name, always a lower case string with no white space.
                  description:
                    type: string
                    description: Plain text describing the role.
      400:
        description: if the request incudes an unknown role.
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to edit requested user_id
      404:
        description: if user_id doesn't exist

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='edit', other_id=user_id)
        user = get_user(user_id)
    if not user:
        abort(404, "user_id {} not found".format(user_id))

    # Don't allow promotion of service accounts
    if user.has_role(ROLE.SERVICE):
        abort(400, "Promotion of service users not allowed")

    if not request.json or 'roles' not in request.json:
        abort(400, "Requires role list")
    remove_if_not_requested = {role.id: role for role in user.roles}
    requested_roles = [r['name'] for r in request.json['roles']]
    matching_roles = Role.query.filter(Role.name.in_(requested_roles)).all()
    if len(matching_roles) != len(requested_roles):
        abort(400, "One or more roles requested not available")
    # Add any requested not already set on user
    for requested_role in matching_roles:
        if requested_role not in user.roles:
            user.roles.append(requested_role)
            auditable_event("added {} to user {}".format(
                requested_role, user.id), user_id=current_user().id)
        else:
            remove_if_not_requested.pop(requested_role.id)

    for stale_role in remove_if_not_requested.values():
        user.roles.remove(stale_role)
        auditable_event("deleted {} from user {}".format(
            stale_role, user.id), user_id=current_user().id)

    if user not in db.session:
        db.session.add(user)
    db.session.commit()

    # Return user's updated role list
    results = [{'name': r.name, 'description': r.description}
            for r in user.roles]
    return jsonify(roles=results)


@user_api.route('/unique_email')
def unique_email():
    """Confirm a given email is unique

    For upfront validation of email addresses, determine if the given
    email is unique - i.e. unknown to the system.  If it is known, but
    belongs to the authenticated user (or user_id if provided), it will
    still be considered unique.

    Returns json unique=True or unique=False
    ---
    tags:
      - User
    operationId: unique_email
    produces:
      - application/json
    parameters:
      - name: email
        in: query
        description:
          email to validate
        required: true
        type: string
      - name: user_id
        in: query
        description:
          optional user_id, defaults to current user, necessary for admins
          editing other users.
        required: false
        type: string
    responses:
      200:
        description:
          Returns JSON describing unique=True or unique=False
        schema:
          id: unique_result
          required:
            - unique
          properties:
            unique:
              type: boolean
              description: result of unique check
      400:
        description: if email param is poorly defined
      401:
        description: if missing valid OAuth token

    """
    email = request.args.get('email')
    if not email or '@' not in email or len(email) < 6:
        abort(400, "requires a valid email address")
    match = User.query.filter_by(email=email)
    assert(match.count() < 2)  # db unique constraint - can't happen, right?
    if match.count() == 1:
        # If the user is the authenticated user or provided user_id,
        # it still counts as unique

        user_id = request.args.get('user_id')
        if not user_id:
            # Note the extra oauth verify step, so this method can also
            # be used by unauth'd users (say during registration).
            valid, req = oauth.verify_request(['email'])
            if valid:
                user_id = req.user.id
            else:
                user = current_user()
                user_id = user.id if user else None
        else:
            user_id = int(user_id)

        result = match.one()
        if user_id != result.id:
            return jsonify(unique=False)
    return jsonify(unique=True)
