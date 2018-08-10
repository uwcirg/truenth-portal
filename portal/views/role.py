"""Role(s) API"""
from flask import Blueprint, abort, jsonify, request

from ..database import db
from ..extensions import oauth
from ..models.role import Role
from ..models.user import current_user, get_user_or_abort
from .crossdomain import crossdomain

role_api = Blueprint('role_api', __name__,)


@role_api.route('/api/roles', methods=('OPTIONS', 'GET'))
@crossdomain(origin='*')
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
                properties:
                  name:
                    type: string
                    description:
                      Role name, always a lower case string with no white space.
                  description:
                    type: string
                    description: Plain text describing the role.
                  display_name:
                    type: string
                    description:
                      Display version of name field, title cased with whitespace
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view roles
    security:
      - Authorization: []

    """
    return jsonify(roles=[r.as_json() for r in Role.query.all()])


@role_api.route('/api/user/<int:user_id>/roles', methods=('OPTIONS', 'GET'))
@crossdomain(origin='*')
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
          $ref: "#/definitions/nested_roles"
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id
    security:
      - Authorization: []

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='view', other_id=user_id)
        user = get_user_or_abort(user_id)

    return jsonify(roles=[r.as_json() for r in user.roles])


@role_api.route('/api/user/<int:user_id>/roles', methods=('POST',))
@oauth.require_oauth()
def add_roles(user_id):
    """Add roles to user, returns simple JSON defining user roles

    Used to add role(s) to a user.  See the PUT version for the idempotent
    mechanism to define the complete set of roles for a user.  This
    endpoint will only POST a new role (or multiple roles) on a user.

    If any of the roles POSTed are already defined for the user, a 409
    will be raised.

    Only the 'name' field of the roles is referenced.  Must match
    current roles in the system.

    Returns a list of all roles associated with user after change.
    ---
    tags:
      - User
      - Role
    operationId: addRoles
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
          $ref: "#/definitions/nested_roles"
    responses:
      200:
        description:
          Returns a list of all roles user belongs to after change.
        schema:
          $ref: "#/definitions/nested_roles"
      400:
        description: if the request includes an unknown role.
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to edit requested user_id
      404:
        description: if user_id doesn't exist
      409:
        description: if any of the given roles are already assigned to the user

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='edit', other_id=user_id)
        user = get_user_or_abort(user_id)
    if not request.json or 'roles' not in request.json:
        abort(400, "Requires role list")

    role_list = [Role.query.filter_by(name=role.get('name')).one()
                 for role in request.json.get('roles')]
    user.add_roles(role_list, acting_user=current_user())
    db.session.commit()

    # Return user's updated role list
    return jsonify(roles=[r.as_json() for r in user.roles])


@role_api.route('/api/user/<int:user_id>/roles', methods=('DELETE',))
@oauth.require_oauth()
def delete_roles(user_id):
    """Delete roles from user, returns simple JSON listing remaining roles

    Used to delete role(s) from a user.  See the PUT version for the
    idempotent mechanism to define the complete set of roles for a user.

    If any of the roles given are not currently defined for the user, a 409
    will be raised.

    Only the 'name' field of the roles is referenced.  Must match
    current roles in the system.

    Returns a list of all roles associated with user after change.
    ---
    tags:
      - User
      - Role
    operationId: deleteRoles
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
          $ref: "#/definitions/nested_roles"
    responses:
      200:
        description:
          Returns a list of all roles user belongs to after change.
        schema:
          $ref: "#/definitions/nested_roles"
      400:
        description: if the request includes an unknown role.
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to edit requested user_id
      404:
        description: if user_id doesn't exist
      409:
        description: if any of the given roles are not currently assigned to the user

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='edit', other_id=user_id)
        user = get_user_or_abort(user_id)
    if not request.json or 'roles' not in request.json:
        abort(400, "Requires role list")

    role_list = [Role.query.filter_by(name=role.get('name')).one()
                 for role in request.json.get('roles')]
    user.delete_roles(role_list, acting_user=current_user())
    db.session.commit()

    # Return user's updated role list
    return jsonify(roles=[r.as_json() for r in user.roles])


@role_api.route('/api/user/<int:user_id>/roles', methods=('PUT',))
@oauth.require_oauth()
def set_roles(user_id):
    """Set roles for user, returns simple JSON defining user roles

    Used to set role assignments for a user.  Include all roles
    the user should be a member of.  If user previously belonged to
    roles not included, the missing roles will be deleted from the user.

    Only the 'name' field of the roles is referenced.  Must match
    current roles in the system.

    Returns a list of all roles associated with user after change.
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
          $ref: "#/definitions/nested_roles"
    responses:
      200:
        description:
          Returns a list of all roles user belongs to after change.
        schema:
          $ref: "#/definitions/nested_roles"
      400:
        description: if the request includes an unknown role.
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
        user = get_user_or_abort(user_id)
    if not request.json or 'roles' not in request.json:
        abort(400, "Requires role list")

    role_list = [Role.query.filter_by(name=role.get('name')).one()
                 for role in request.json.get('roles')]
    user.update_roles(role_list, acting_user=current_user())
    db.session.commit()

    # Return user's updated role list
    return jsonify(roles=[r.as_json() for r in user.roles])
