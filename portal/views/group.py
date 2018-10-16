"""Group view methods"""
from flask import Blueprint, abort, jsonify, request
from flask_user import roles_required

from ..audit import auditable_event
from ..database import db
from ..extensions import oauth
from ..models.group import Group
from ..models.role import ROLE
from ..models.user import current_user
from .crossdomain import crossdomain

group_api = Blueprint('group_api', __name__, url_prefix='/api/group')


@group_api.route('/')
@crossdomain()
@oauth.require_oauth()
def current_groups():
    """Returns simple JSON defining all current groups

    Returns a list of all known groups.  Groups are used to logically
    associate users, see `role` for access issues.

    ---
    tags:
      - Group
    operationId: current_groups
    produces:
      - application/json
    responses:
      200:
        description: Returns a list of all known groups.
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
        description: if missing valid OAuth token
    security:
      - ServiceToken: []

    """
    results = [g.as_json() for g in Group.query.all()]
    return jsonify(groups=results)


@group_api.route('/<string:group_name>')
@crossdomain()
@oauth.require_oauth()
def group_by_name(group_name):
    """Returns simple JSON for the requested group

    ---
    tags:
      - Group
    operationId: group_by_name
    parameters:
      - name: group_name
        in: path
        description: Group name
        required: true
        type: string
    produces:
      - application/json
    responses:
      200:
        description: Returns simple JSON for the named group
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
        description: if missing valid OAuth token
      404:
        description: if named group doesn't exist
    security:
      - ServiceToken: []

    """
    g = Group.query.filter_by(name=group_name).first()
    if not g:
        abort(404, "Group {n} not found".format(n=group_name))
    return jsonify(group=g.as_json())


@group_api.route('/', methods=('POST',))
@crossdomain()
@oauth.require_oauth()  # for service token access, oauth must come first
@roles_required([ROLE.ADMIN.value, ROLE.SERVICE.value])
def add_group():
    """Add new group

    POST simple JSON defining new group.

    ---
    tags:
      - Group
    operationId: add_group
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          id: group_definition
          description: Group details including name and description
          required:
            - name
            - description
          properties:
            name:
              type: string
              description:
                Group name, limited to lower case letters and underscores.
            description:
              type: string
              description:
                Plain text detailing the groups use or members.
    responses:
      200:
        description: successful operation
        schema:
          id: response_ok
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      400:
        description:
          if input isn't valid or if matching group name already exists
      401:
        description: if missing valid OAuth token
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """
    if not (request.json and 'name' in request.json and 'description' in
            request.json):
        abort(400,
              "Requires valid JSON including a group name and description")
    name = request.json['name']
    match = Group.query.filter_by(name=name).first()
    if match:
        abort(400,
              "{name} already exists, can't redefine".format(name=name))

    name = Group.validate_name(name)
    g = Group(name=name, description=request.json['description'])
    db.session.add(g)
    db.session.commit()
    auditable_event(
        "{g} added".format(g=g), user_id=current_user().id,
        subject_id=current_user().id, context='group')
    return jsonify(message="ok")


@group_api.route('/<string:group_name>', methods=('PUT',))
@crossdomain()
@oauth.require_oauth()  # for service token access, oauth must come first
@roles_required([ROLE.ADMIN.value, ROLE.SERVICE.value])
def edit_group(group_name):
    """Edit an existing group

    PUT simple JSON defining changes to an existing group.

    ---
    tags:
      - Group
    operationId: edit_group
    produces:
      - application/json
    parameters:
      - name: group_name
        in: path
        description: Group name
        required: true
        type: string
      - in: body
        name: body
        schema:
          id: group_definition
          description: Group details including name and description
          required:
            - name
            - description
          properties:
            name:
              type: string
              description:
                Group name, limited to lower case letters and underscores.
            description:
              type: string
              description:
                Plain text detailing the groups use or members.
    responses:
      200:
        description: successful operation
        schema:
          id: response_ok
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      400:
        description:
          if input isn't valid or if matching group name already exists
      401:
        description: if missing valid OAuth token
      404:
        description: if group by group_name can't be found
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """
    g = Group.query.filter_by(name=group_name).first()
    if not g:
        abort(404, "Group {n} not found".format(n=group_name))

    if not (request.json and 'name' in request.json and 'description' in
            request.json):
        abort(400,
              "Requires valid JSON including a group name and description")

    g.name = Group.validate_name(request.json['name'])
    g.description = request.json['description']
    db.session.commit()
    auditable_event(
        "{g} updated".format(g=g), user_id=current_user().id,
        subject_id=current_user().id, context='group')
    return jsonify(message="ok")
