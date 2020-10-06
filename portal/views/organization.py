"""Organization related views module"""
import json

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
)
from flask_user import roles_required
from sqlalchemy import and_, exc

from ..audit import auditable_event
from ..cache import FIVE_MINS, cache, request_args_in_key
from ..database import db
from ..extensions import oauth
from ..models.coding import Coding
from ..models.identifier import Identifier
from ..models.organization import Organization, OrganizationIdentifier, OrgTree
from ..models.reference import MissingReference, Reference
from ..models.role import ROLE
from ..models.user import current_user, get_user
from ..system_uri import IETF_LANGUAGE_TAG, PRACTICE_REGION
from .crossdomain import crossdomain

org_api = Blueprint('org_api', __name__, url_prefix='/api')


@org_api.route('/organization')
@crossdomain()
@oauth.require_oauth()
@cache.cached(timeout=FIVE_MINS, key_prefix=request_args_in_key)
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
      - name: tree_view
        in: query
        description:
            If given a `True` value, alters the return type to HTML and
            generates a `tree` view of the organization hierarchy for easier
            human comprehension of the structure.  Can NOT be combined with
            other filters or search parameters.
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
    security:
      - ServiceToken: []

    """
    filter = None
    found_ids = []
    system, value, tree_view = None, None, None
    for k, v in request.args.items():
        if k == 'state':
            if not v or len(v) != 2:
                abort(400, "state search requires two letter state code")
            region = 'state:{}'.format(v.upper())

            query = OrganizationIdentifier.query.join(
                Identifier).filter(and_(
                    OrganizationIdentifier.identifier_id == Identifier.id,
                    Identifier.system == PRACTICE_REGION,
                    Identifier._value == region))
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
        elif k == 'tree_view':
            tree_view = v and v.lower() == 'true'
        else:
            abort(
                400, "only search on `state`, `filter` or `system` AND `value`"
                     " are available at this time")

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
    if tree_view:
        if matching_orgs:
            abort(400, "Can't combine search filters with `tree_view`")
        return render_template('org_tree.html', bundle=bundle)
    return jsonify(bundle)


@org_api.route('/organization/<string:id_or_code>')
@crossdomain()
@oauth.require_oauth()
def organization_get(id_or_code):
    """Access to the requested organization as a FHIR resource

    If 'system' param is provided, looks up the organization by identifier,
    using the `id_or_code` string as the identifier value; otherwise,
    treats `id_or_code` as the organization.id

    ---
    operationId: organization_get
    tags:
      - Organization
    produces:
      - application/json
    parameters:
      - name: id_or_code
        in: path
        description: TrueNTH organization ID OR Identifier value code
        required: true
        type: string
      - name: system
        in: query
        description: Identifier system
        required: false
        type: string
      - name: include_inherited_attributes
        in: query
        description: include attributes defined at a parent or higher level
        required: false
        type: string
    responses:
      200:
        description:
          Returns the requested organization as a FHIR [organization
          resource](https://www.hl7.org/fhir/DSTU2/organization.html) in JSON.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """
    system = request.args.get('system')
    if system:
        query = Organization.query.join(
            OrganizationIdentifier).join(
            Identifier).filter(and_(
                Organization.id == OrganizationIdentifier.organization_id,
                OrganizationIdentifier.identifier_id == Identifier.id,
                Identifier.system == system,
                Identifier._value == id_or_code))
        if query.count() == 1:
            org = query.first()
        else:
            abort(
                404, 'no organization found with identifier: '
                     'system `{}`, value `{}`'.format(system, id_or_code))
    else:
        try:
            organization_id = int(id_or_code)
            org = Organization.query.get_or_404(organization_id)
        except ValueError:
            abort(
                400, "invalid input '{}' - expected integer without system "
                     "parameter".format(id_or_code))

    include_inherited = request.args.get(
        'included_inherited_attributes', 'false').lower() != 'false'
    return jsonify(org.as_fhir(
        include_empties=False, include_inherited=include_inherited))


@org_api.route('/organization/<int:organization_id>', methods=('DELETE',))
@crossdomain()
@roles_required(ROLE.ADMIN.value)
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
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """
    org = Organization.query.get_or_404(organization_id)
    try:
        db.session.delete(org)
        db.session.commit()
    except exc.IntegrityError as e:
        message = "Cannot delete organization with related entities"
        current_app.logger.warn(message + str(e), exc_info=True)
        abort(message, 400)
    auditable_event(
        "deleted {}".format(org), user_id=current_user().id,
        subject_id=current_user().id, context='organization')
    OrgTree.invalidate_cache()
    return jsonify(message='deleted organization {}'.format(org))


@org_api.route('/organization', methods=('POST',))
@crossdomain()
@oauth.require_oauth()  # for service token access, oauth must come first
@roles_required([ROLE.ADMIN.value, ROLE.SERVICE.value])
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
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """
    if (not request.json or 'resourceType' not in request.json or
            request.json['resourceType'] != 'Organization'):
        abort(400, "Requires FHIR resourceType of 'Organization'")
    try:
        org = Organization.from_fhir(request.json)
    except MissingReference as e:
        abort(400, str(e))
    db.session.add(org)
    db.session.commit()
    auditable_event("added new organization {}".format(org),
                    user_id=current_user().id, subject_id=current_user().id,
                    context='organization')
    OrgTree.invalidate_cache()
    return jsonify(org.as_fhir(include_empties=False))


@org_api.route('/organization/<int:organization_id>', methods=('PUT',))
@crossdomain()
@oauth.require_oauth()  # for service token access, oauth must come first
@roles_required([ROLE.ADMIN.value, ROLE.SERVICE.value])
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
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """
    if (not request.json or 'resourceType' not in request.json or
            request.json['resourceType'] != 'Organization'):
        abort(400, "Requires FHIR resourceType of 'Organization'")
    org = Organization.query.get_or_404(organization_id)
    try:
        # As we allow partial updates, first obtain a full representation
        # of this org, and update with any provided elements
        complete = org.as_fhir(include_empties=True)
        complete.update(request.json)
        org.update_from_fhir(complete)
    except MissingReference as e:
        abort(400, str(e))
    db.session.commit()
    auditable_event("updated organization from input {}".format(
        json.dumps(request.json)), user_id=current_user().id,
        subject_id=current_user().id, context='organization')
    OrgTree.invalidate_cache()
    return jsonify(org.as_fhir(include_empties=False))


@org_api.route('/user/<int:user_id>/organization')
@crossdomain()
@oauth.require_oauth()
def user_organizations(user_id):
    """Obtain list of organization references currently associated with user

    ---
    tags:
      - User
      - Organization
    operationId: user_organizations
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
        description: return list of user's organizations by reference
        schema:
          id: organization_references
          properties:
            organizations:
              type: array
              items:
                type: object
                required:
                  - reference
                properties:
                  reference:
                    type: string
                    description: FHIR compliant reference to an organization
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to edit requested user_id
      404:
        description: if user_id doesn't exist
    security:
      - ServiceToken: []

    """
    # Return user's current organizations
    user = get_user(
        user_id, 'view', allow_on_url_authenticated_encounters=True)
    return jsonify(organizations=[
        Reference.organization(org.id).as_fhir()
        for org in user.organizations])


@org_api.route('/user/<int:user_id>/organization', methods=('POST',))
@crossdomain()
@oauth.require_oauth()
def add_user_organizations(user_id):
    """Associate organization with user via reference

    POST a list of references to each existing organization to associate with
    given user.  These will be added to the user's current organizations.

    Both organization reference formats are supported, i.e.:

        {'organizations': [
            {'reference': 'api/organization/1001'},
            {'reference': 'api/organization/123-45?system=http://pcctc.org/'}
        ]}

    Additional attributes may be applied to the user, from the named
    organization's matching defaults.  For example, both the default
    timezone and the language may be assigned using the respective values:

        {'organizations': [
            {'reference': 'api/organizations/1001',
             'language': 'apply_to_user',
             'timezone': 'apply_to_user'}
        ]}

    If user is already associated with one or more of the posted organizations,
    a 409 will be raised.

    ---
    tags:
      - User
      - Organization
    operationId: add_user_organizations
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
          $ref: "#/definitions/organization_references"
    responses:
      200:
        description:
          return list of user's organizations by reference after change
        schema:
          $ref: "#/definitions/organization_references"
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
      - OAuth2AuthzFlow: []

    """
    user = get_user(user_id, 'edit')
    if not request.json or 'organizations' not in request.json:
        abort(400, "Requires `organizations` list")

    # validate input - don't allow multiple orgs with `apply_to_user`
    # attributes for any given field
    applied_fields = []

    def apply_defaults(item, org, applied):
        for field in 'timezone', 'language':
            if field in item:
                if item[field] != 'apply_to_user':
                    abort(400, "expected 'apply_to_user' on {}".format(field))
                if field in applied:
                    abort(400, "can't apply defaults from more than one org")
                if field == 'language':
                    # Org's default_locale respects the org tree inheritance,
                    # but only returns the 'code' - need full Coding to set
                    if not org.default_locale:
                        abort(
                            400, "can't apply language from org w/o a value")
                    locale_code = Coding.query.filter(
                        Coding.system == IETF_LANGUAGE_TAG).filter(
                        Coding.code == org.default_locale).one()
                    user.locale = (locale_code.code, locale_code.display)
                else:
                    setattr(user, field, getattr(org, field))
                applied.append(field)

    for item in request.json.get('organizations'):
        try:
            org = Reference.parse(item)
        except MissingReference as e:
            abort(400, "Organization {}".format(e))
        apply_defaults(item, org, applied_fields)
        if not isinstance(org, Organization):
            abort(400, "Expecting only `Organization` references")
        if org in user.organizations:
            abort(
                409,
                "POST restricted to organizations not already assigned to "
                "user")
        user.organizations.append(org)
        auditable_event(
            message='Added {}'.format(org), user_id=current_user().id,
            subject_id=user.id, context='organization')
    db.session.commit()

    # Return current organizations

    return jsonify(organizations=[
        Reference.organization(org.id).as_fhir()
        for org in user.organizations])
