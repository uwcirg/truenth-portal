"""Organization related views module"""
from flask import abort, current_app, Blueprint, jsonify, request
from flask_user import roles_required
import json
from sqlalchemy import exc

from ..audit import auditable_event
from ..extensions import db, oauth
from ..models.organization import Organization, OrgTree
from ..models.reference import MissingReference
from ..models.role import ROLE
from ..models.user import current_user


org_api = Blueprint('org_api', __name__, url_prefix='/api')


@org_api.route('/organization')
@oauth.require_oauth()
def organization_list():
    """Obtain a bundle (list) of all registered organizations

    Returns the JSON FHIR bundle of organizations as known to the system.
    ---
    operationId: organization_list
    tags:
      - Organization
    produces:
      - application/json
    responses:
      200:
        description:
          Returns a FHIR bundle of [organization
          resources](http://www.hl7.org/fhir/patient.html) in JSON.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    bundle = Organization.generate_bundle()
    return jsonify(bundle)


@org_api.route('/organization/<int:organization_id>')
@oauth.require_oauth()
def organization_get(organization_id):
    """Access to the requested organization as a FHIR resource

    ---
    operationId: organization_get
    tags:
      - Organization
    produces:
      - application/json
    parameters:
      - name: organization_id
        in: path
        description: TrueNTH organization ID
        required: true
        type: integer
        format: int64
    responses:
      200:
        description:
          Returns the requested organization as a FHIR [organization
          resource](http://www.hl7.org/fhir/patient.html) in JSON.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    org = Organization.query.get_or_404(organization_id)
    return jsonify(org.as_fhir())


@org_api.route('/organization/<int:organization_id>', methods=('DELETE',))
@roles_required(ROLE.ADMIN)
@oauth.require_oauth()
def organization_delete(organization_id):
    """Delete the requested organization

    NB - only organizations without any relationships to entities such
    as patients and other organizations may be deleted.
    ---
    tags:
      - Organization
    operationId: organization_delete
    produces:
      - application/json
    parameters:
      - name: organization_id
        in: path
        description: TrueNTH organization ID
        required: true
        type: integer
        format: int64
    responses:
      200:
        description: message reporting successful deletion
      400:
        description: Cannot delete organization with related entities
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id

    """
    org = Organization.query.get_or_404(organization_id)
    try:
        db.session.delete(org)
        db.session.commit()
    except exc.IntegrityError, e:
        message = "Cannot delete organization with related entities"
        current_app.logger.warn(message + str(e), exc_info=True)
        abort(message, 400)
    auditable_event("deleted {}".format(org), user_id=current_user().id)
    OrgTree.invalidate_cache()
    return jsonify(message='deleted organization {}'.format(org))


@org_api.route('/organization', methods=('POST',))
@roles_required([ROLE.ADMIN, ROLE.SERVICE])
@oauth.require_oauth()
def organization_post():
    """Add a new organization.  Updates should use PUT

    Returns the JSON FHIR organization as known to the system after adding.

    Submit JSON format [Organization
    Resource](https://www.hl7.org/fhir/organization.html) to add an
    organization.

    Include an **identifier** with system of
    http://us.truenth.org/identity-codes/shortcut-alias to name a shortcut
    alias for the organization, useful at `/go/<alias>`.

    A resource mentioned as partOf the given organization must exist as a
    prerequisit or a 400 will result.

    ---
    operationId: organization_post
    tags:
      - Organization
    produces:
      - application/json
    parameters:
      - name: organization_id
        in: path
        description: TrueNTH organization ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: FHIROrganization
          required:
            - resourceType
          properties:
            resourceType:
              type: string
              description: defines FHIR resource type, must be Organization
    responses:
      200:
        description:
          Returns updated [FHIR organization
          resource](http://www.hl7.org/fhir/patient.html) in JSON.
      400:
        description:
          if partOf resource does not exist
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    if not request.json or 'resourceType' not in request.json or\
            request.json['resourceType'] != 'Organization':
        abort(400, "Requires FHIR resourceType of 'Organization'")
    try:
        org = Organization.from_fhir(request.json)
    except MissingReference, e:
        abort(400, str(e))
    db.session.add(org)
    db.session.commit()
    auditable_event("added new organization {}".format(org),
                    user_id=current_user().id)
    OrgTree.invalidate_cache()
    return jsonify(org.as_fhir())


@org_api.route('/organization/<int:organization_id>', methods=('PUT',))
@roles_required([ROLE.ADMIN, ROLE.SERVICE])
@oauth.require_oauth()
def organization_put(organization_id):
    """Update organization via FHIR Resource Organization. New should POST

    Submit JSON format [Organization
    Resource](https://www.hl7.org/fhir/organization.html) to update an existing
    organization.

    Include an **identifier** with system of
    http://us.truenth.org/identity-codes/shortcut-alias to name a shortcut
    alias for the organization, useful at `/go/<alias>`.

    A resource mentioned as partOf the given organization must exist as a
    prerequisit or a 400 will result.

    ---
    operationId: organization_put
    tags:
      - Organization
    produces:
      - application/json
    parameters:
      - name: organization_id
        in: path
        description: TrueNTH organization ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: FHIROrganization
          required:
            - resourceType
          properties:
            resourceType:
              type: string
              description: defines FHIR resource type, must be Organization
    responses:
      200:
        description:
          Returns updated [FHIR organization
          resource](http://www.hl7.org/fhir/patient.html) in JSON.
      400:
        description:
          if partOf resource does not exist
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    if not request.json or 'resourceType' not in request.json or\
            request.json['resourceType'] != 'Organization':
        abort(400, "Requires FHIR resourceType of 'Organization'")
    org = Organization.query.get_or_404(organization_id)
    try:
        org.update_from_fhir(request.json)
    except MissingReference, e:
        abort(400, str(e))
    db.session.commit()
    auditable_event("updated organization from input {}".format(
        json.dumps(request.json)), user_id=current_user().id)
    OrgTree.invalidate_cache()
    return jsonify(org.as_fhir())
