"""Clinician API view functions"""
from flask import Blueprint, jsonify, request, url_for
from flask_user import roles_required

from ..extensions import oauth
from ..models.fhir import bundle_results
from ..models.identifier import Identifier
from ..models.organization import org_restriction_by_role
from ..models.practitioner import Practitioner
from ..models.role import Role, ROLE
from ..models.user import User, UserOrganization, UserRoles, current_user
from ..system_uri import TRUENTH_ID, TRUENTH_PI
from .crossdomain import crossdomain

clinician_api = Blueprint('clinician_api', __name__)


def clinician_name_map():
    roles = [ROLE.CLINICIAN.value, ROLE.PRIMARY_INVESTIGATOR.value]
    query = User.query.join(UserRoles).filter(
        User.deleted_id.is_(None)).filter(
        UserRoles.user_id == User.id).join(Role).filter(
        UserRoles.role_id == Role.id).filter(
        Role.name.in_(roles))

    _clinician_name_map = {None: None}
    for clinician in query:
        _clinician_name_map[clinician.id] = f"{clinician.last_name}, {clinician.first_name}"
    return _clinician_name_map


def clinician_query(acting_user, org_filter=None, include_staff=False):
    """Builds a live query for all clinicians the acting user can view"""
    roles = [ROLE.CLINICIAN.value, ROLE.PRIMARY_INVESTIGATOR.value]
    if include_staff:
        roles.append(ROLE.STAFF.value)
    query = User.query.join(UserRoles).filter(
        User.deleted_id.is_(None)).filter(
        UserRoles.user_id == User.id).join(Role).filter(
        UserRoles.role_id == Role.id).filter(
        Role.name.in_(roles))

    limit_to_orgs = org_restriction_by_role(acting_user, org_filter)
    if limit_to_orgs:
        query = query.join(UserOrganization).filter(
            UserOrganization.user_id == User.id).filter(
            UserOrganization.organization_id.in_(limit_to_orgs))

    return query


@clinician_api.route('/api/clinician')
@crossdomain()
@roles_required([
    ROLE.CLINICIAN.value,
    ROLE.STAFF.value,
    ROLE.STAFF_ADMIN.value])
@oauth.require_oauth()
def clinician_search():
    """Obtain a bundle (list) of all clinicians current_user can view

    Returns a JSON FHIR bundle of clinicians and their organization.
    Results limited to clinicians with a common organization, or a child
    of the current user's organization(s).

    Can further limit results to those at or below a filter organization,
    such as a patient's org, by including query parameter
     ``/api/clinician?organization_id=###``

    ---
    operationId: clinician_search
    tags:
      - Clinician
    parameters:
      - name: org_filter
        in: query
        description:
            Limit the results beyond the current_user's view by including
            organization identifiers
            `/api/clinician?organization_id=146999`
        required: true
        type: string
    produces:
      - application/json
    responses:
      200:
        description:
          Returns a FHIR bundle of clinicians as [practitioner
          resources](http://www.hl7.org/fhir/DSTU2/practitioner.html) in JSON.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
    security:
      - ServiceToken: []

    """
    clinicians = []
    org_filter = request.args.getlist('organization_id', int)
    for user in clinician_query(current_user(), org_filter):
        identifiers = [
            Identifier(use='official', system=TRUENTH_ID, value=user.id)
        ]
        if user.has_role(ROLE.PRIMARY_INVESTIGATOR.value):
            identifiers.append(
                Identifier(use='secondary', system=TRUENTH_PI, value=True)
            )
        clinicians.append(Practitioner(
            first_name=user.first_name,
            last_name=user.last_name,
            identifiers=identifiers).as_fhir())

    link = {
        'rel': 'self', 'href': url_for(
            'clinician_api.clinician_search', _external=True)}

    return jsonify(bundle_results(elements=clinicians, links=[link]))
