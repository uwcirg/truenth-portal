"""Organization related views module"""
from flask import abort, current_app, Blueprint, jsonify, request
from flask_user import roles_required
import json
from sqlalchemy import exc, and_

from ..audit import auditable_event
from ..database import db
from ..extensions import oauth
from ..models.identifier import Identifier
from ..models.organization import Organization, OrganizationIdentifier, OrgTree
from ..models.reference import MissingReference
from ..models.role import ROLE
from ..models.user import current_user
from ..system_uri import PRACTICE_REGION


org_api = Blueprint('org_api', __name__, url_prefix='/api')


@org_api.route('/organization')
@oauth.require_oauth()
def organization_search():
    """Obtain a bundle (list) of all matching organizations

    Takes key=value pairs to look up.

    Example search:
        /api/organization?state=NJ

    Or to lookup by identifier, include system and value:
        /api/organization?system=http%3A%2F%2Fpcctc.org%2F&value=146-31

    Returns a JSON FHIR bundle of organizations as per given search terms.
    Without any search terms, returns all organizations known to the system.
    If search terms are provided but no matching organizations are found,
    a 404 is returned.

    ---
    operationId: organization_search
    tags:
      - Organization
    parameters:
      - name: search_parameters
        in: query
        description:
            Search parameters, such as `state`, which should be the two
            letter state code.
        required: false
        type: string
      - name: filter
        in: query
        description:
            Filter to apply to search, such as `leaves` to restrict results
            to just the leaf nodes of the organization tree.
        required: false
        type: string
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
    filter = None
    found_ids = []
    system, value = None, None
    for k,v in request.args.items():
        if k == 'state':
            if not v or len(v) != 2:
                abort(400, "state search requires two letter state code")
            region = 'state:{}'.format(v.upper())

            query = OrganizationIdentifier.query.join(
                Identifier).filter(and_(
                    OrganizationIdentifier.identifier_id==Identifier.id,
                    Identifier.system==PRACTICE_REGION,
                    Identifier._value==region))
            found_ids = [oi.organization_id for oi in query]
            if not found_ids:
                abort(404, "no organzations found for state {}".format(v))
        elif k == 'filter':
            filter = v
            if not filter == 'leaves':
                abort(
                    400, "unknown filter request '{}' - expecting "
                    "'leaves'".format(filter))
        elif k == 'system':
            system = v
        elif k == 'value':
            value = v
        else:
            abort(400, "only search on `state`, `filter` or `system` AND `value` "
                  "are available at this time")

    if system and value:
        query = OrganizationIdentifier.query.join(
            Identifier).filter(and_(
                OrganizationIdentifier.identifier_id == Identifier.id,
                Identifier.system == system,
                Identifier._value == value))
        found_ids = [oi.organization_id for oi in query]
        if not found_ids:
            abort(
                404, "no organzations found for system, value {}, {}".format(
                    system, value))

    # Apply search on org fields like inheritence - include any children
    # of the matching nodes.  If filter is set, apply to results.
    ot = OrgTree()
    matching_orgs = set()

    # Lookout for filter w/o a search term, use top level ids in this case
    if filter and not found_ids:
        found_ids = ot.all_top_level_ids()

    for org in found_ids:
        if filter == 'leaves':
            matching_orgs |= set(ot.all_leaves_below_id(org))
        else:
            matching_orgs |= set(ot.here_and_below_id(org))

    bundle = Organization.generate_bundle(matching_orgs, include_empties=False)
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
    return jsonify(org.as_fhir(include_empties=False))


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
    auditable_event("deleted {}".format(org), user_id=current_user().id,
        subject_id=current_user().id, context='organization')
    OrgTree.invalidate_cache()
    return jsonify(message='deleted organization {}'.format(org))


@org_api.route('/organization', methods=('POST',))
@oauth.require_oauth()  # for service token access, oauth must come first
@roles_required([ROLE.ADMIN, ROLE.SERVICE])
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
                    user_id=current_user().id, subject_id=current_user().id,
                    context='organization')
    OrgTree.invalidate_cache()
    return jsonify(org.as_fhir(include_empties=False))


@org_api.route('/organization/<int:organization_id>', methods=('PUT',))
@oauth.require_oauth()  # for service token access, oauth must come first
@roles_required([ROLE.ADMIN, ROLE.SERVICE])
def organization_put(organization_id):
    """Update organization via FHIR Resource Organization. New should POST

    Submit JSON format [Organization
    Resource](https://www.hl7.org/fhir/organization.html) to update an
    existing organization.

    Include an **identifier** with system of
    http://us.truenth.org/identity-codes/shortcut-alias to name a shortcut
    alias for the organization, useful at `/go/<alias>`.  NB, including a
    partial list of identifiers will result in the non mentioned identifiers
    being deleted.  Consider calling GET first.

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
        # As we allow partial updates, first obtain a full representation
        # of this org, and update with any provided elements
        complete = org.as_fhir(include_empties=True)
        complete.update(request.json)
        org.update_from_fhir(complete)
    except MissingReference, e:
        abort(400, str(e))
    db.session.commit()
    auditable_event("updated organization from input {}".format(
        json.dumps(request.json)), user_id=current_user().id,
        subject_id=current_user().id, context='organization')
    OrgTree.invalidate_cache()
    return jsonify(org.as_fhir(include_empties=False))
