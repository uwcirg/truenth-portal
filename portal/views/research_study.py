from flask import Blueprint, jsonify

from ..extensions import oauth
from ..models.organization import (
    OrgTree,
    OrganizationResearchProtocol,
)
from ..models.research_protocol import ResearchProtocol
from ..models.research_study import ResearchStudy
from ..models.role import ROLE
from ..models.user import get_user
from .crossdomain import crossdomain

research_study_api = Blueprint('research_study_api', __name__)


@research_study_api.route('/api/user/<int:user_id>/research_study')
@crossdomain()
@oauth.require_oauth()
def rs_for_user(user_id):
    """Returns simple JSON for research study user is eligible for

    NB a user may be "eligible" but not yet "ready" for a given study. Use
    ``qb_status.patient_research_study_status()`` to check.

    ---
    tags:
      - User
      - ResearchStudy
    operationId: research_studies_for_user
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID, typically subject or staff
        required: true
        type: integer
        format: int64
    produces:
      - application/json
    responses:
      200:
        description:
          Returns the list of research_studies the requested user is
          associated with.
        schema:
          id: nested_research_studies
          properties:
            research_study:
              type: array
              items:
                type: object
                required:
                  - title
                properties:
                  title:
                    type: string
                    description: Research study title
                  resourceType:
                    type: string
                    description: FHIR like resourceType, "ResearchStudy"
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id
    security:
      - ServiceToken: []

    """
    user = get_user(
        user_id, 'view', allow_on_url_authenticated_encounters=True)
    if user.has_role(ROLE.PATIENT.value):
        study_ids = ResearchStudy.assigned_to(user)
    else:
        # Assume some staff like role - find all research studies
        # in the org tree at, above or below all of the user's orgs
        orgs = set()
        ot = OrgTree()
        for org in user.organizations:
            orgs.update(ot.at_and_above_ids(org.id))
            orgs.update(ot.here_and_below_id(org.id))
        studies = OrganizationResearchProtocol.query.filter(
            OrganizationResearchProtocol.organization_id.in_(
                tuple(orgs))).join(
            ResearchProtocol,
            OrganizationResearchProtocol.research_protocol_id ==
            ResearchProtocol.id).with_entities(
            ResearchProtocol.research_study_id).distinct()
        study_ids = [s.research_study_id for s in studies]
        study_ids.sort()

    return jsonify(research_study=[
        ResearchStudy.query.get(r).as_fhir() for r in study_ids])
