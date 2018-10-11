"""Identifier API"""
from flask import Blueprint, abort, jsonify, request

from ..audit import auditable_event
from ..database import db
from ..extensions import oauth
from ..models.identifier import Identifier
from ..models.user import current_user, get_user_or_abort
from ..system_uri import TRUENTH_ID, TRUENTH_USERNAME
from .crossdomain import crossdomain

identifier_api = Blueprint('identifier_api', __name__)


@identifier_api.route(
    '/api/user/<int:user_id>/identifier',
    methods=('OPTIONS', 'GET'))
@crossdomain()
@oauth.require_oauth()
def identifiers(user_id):
    """Returns list of user's current identifiers

    ---
    tags:
      - User
    operationId: identifiers
    produces:
      - application/json
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
    responses:
      200:
        description: successful operation
        schema:
          id: nested_identifiers
          properties:
            identifier:
              type: array
              items:
                type: object
                required:
                  - system
                  - value
                properties:
                  system:
                    type: string
                    description: uri namespace for the identifier value
                  value:
                    type: string
                    description: unique value for given system namespace
                  use:
                    type: string
                    description: usual | official | temp | secondary (If known)
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to edit requested user_id
      404:
        description: if user_id doesn't exist
      409:
        description: if any of the given identifiers are already assigned to the user
    security:
      - ServiceToken: []

    """
    current_user().check_role(permission='view', other_id=user_id)
    user = get_user_or_abort(user_id)

    # Return current identifiers
    return jsonify(identifier=[i.as_fhir() for i in user.identifiers])


@identifier_api.route(
    '/api/user/<int:user_id>/identifier',
    methods=('OPTIONS', 'POST'))
@crossdomain()
@oauth.require_oauth()
def add_identifier(user_id):
    """Add additional identifier(s) to a user

    Restrictions apply - adding identifiers with system
    ``http://us.truenth.org/identity-codes/TrueNTH-identity`` or
    ``http://us.truenth.org/identity-codes/TrueNTH-username`` will raise
    a 409

    returns modified, complete list of user's identifiers

    ---
    tags:
      - User
    operationId: addIdentifier
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
          $ref: "#/definitions/nested_identifiers"
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to edit requested user_id
      404:
        description: if user_id doesn't exist
      409:
        description: if any of the given identifiers are already assigned to the user
    security:
      - ServiceToken: []

    """
    current_user().check_role(permission='edit', other_id=user_id)
    user = get_user_or_abort(user_id)
    if not request.json or 'identifier' not in request.json:
        abort(400, "Requires identifier list")

    # Prevent edits to internal identifiers
    restricted_systems = (TRUENTH_ID, TRUENTH_USERNAME)
    allowed = [
        i for i in request.json.get('identifier')
        if i.get('system') not in restricted_systems]
    if len(allowed) != len(request.json.get('identifier')):
        abort(409, "Edits to restricted system not allowed")

    for item in allowed:
        ident = Identifier.from_fhir(item).add_if_not_found()
        if ident in user.identifiers:
            abort(
                409,
                "POST restricted to identifiers not already assigned to user")
        auditable_event(
            message='Added {}'.format(ident),
            user_id=current_user().id, subject_id=user.id, context='user')
        user._identifiers.append(ident)
    db.session.commit()

    # Return current identifiers after change
    return jsonify(identifier=[i.as_fhir() for i in user.identifiers])
