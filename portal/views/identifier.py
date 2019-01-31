"""Identifier API"""
from flask import Blueprint, abort, jsonify, request
from werkzeug.exceptions import Conflict

from ..audit import auditable_event
from ..database import db
from ..extensions import oauth
from ..models.identifier import (
    Identifier,
    UserIdentifier,
    parse_identifier_params,
)
from ..models.user import current_user, get_user_or_abort
from .crossdomain import crossdomain

identifier_api = Blueprint('identifier_api', __name__)


@identifier_api.route('/api/user/<int:user_id>/identifier')
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


@identifier_api.route('/api/user/<int:user_id>/identifier', methods=('POST',))
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

    for i in request.json.get('identifier'):
        identifier = Identifier.from_fhir(i).add_if_not_found()
        user.add_identifier(identifier)
        auditable_event(
            message='Added {}'.format(identifier),
            user_id=current_user().id, subject_id=user.id, context='user')
    db.session.commit()

    # Return current identifiers after change
    return jsonify(identifier=[i.as_fhir() for i in user.identifiers])


@identifier_api.route('/api/user/<int:user_id>/unique')
@crossdomain()
def unique_user_identifier(user_id):
    """Confirm a given identifier is unique (if it uses a controlled system)

    Requires query string identifier pattern:
        ?identifier=<system>|<value>

    For upfront validation of user identifiers, determine if the given
    identifier is unique - i.e. not already assigned to another user.

    If it is assigned, but belongs to the given user_id it will still
    be considered unique.

    If it is assigned, but belongs to a deleted user, it will still be
    considered unique.

    Returns json unique=True or unique=False
    ---
    tags:
      - User
    operationId: unique_user_identifier
    produces:
      - application/json
    parameters:
      - name: identifier_parameters
        in: query
        description:
            Identifier parameter, URL-encode the `system` and `value`
            using '|' (pipe) delimiter, i.e.
            `api/user/<user_id>/unique?identifier=http://fake.org/id|12a7`
        required: true
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
    security:
      - ServiceToken: []

    """
    user = get_user_or_abort(user_id)
    system, value = parse_identifier_params(request.args.get('identifier'))
    identifier = Identifier(system=system, value=value).add_if_not_found()
    try:
        result = UserIdentifier.check_unique(user, identifier)
    except Conflict:
        result = False
    return jsonify(unique=result)
