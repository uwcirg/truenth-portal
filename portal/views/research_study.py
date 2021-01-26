from flask import Blueprint, abort, jsonify

from ..extensions import oauth
from ..models.organization import (
    OrgTree,
    OrganizationResearchProtocol,
)
from ..models.qb_status import patient_research_study_status
from ..models.research_protocol import ResearchProtocol
from ..models.research_study import ResearchStudy
from ..models.role import ROLE
from ..models.user import get_user
from .crossdomain import crossdomain

research_study_api = Blueprint('research_study_api', __name__)


@research_study_api.route('/api/patient/<int:user_id>/research_study')
@crossdomain()
@oauth.require_oauth()
def rs_for_patient(user_id):
    """Returns simple JSON for patient's research study status

    ---
    tags:
      - Patient
      - ResearchStudy
    operationId: research_studies_for_patient
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
          Returns the list of research_studies and status the requested
          patient is eligible for.
        schema:
          id: nested_research_study_status
          properties:
            research_study_status:
              type: array
              items:
                type: object
                required:
                  - eligible
                  - ready
                properties:
                  eligible:
                    type: boolean
                    description: is patient eligible (not necessarily ready) for study
                  ready:
                    type: boolean
                    description: true if patient is ready for given study
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id
    security:
      - ServiceToken: []

    """
    user = get_user(
        user_id, 'view', allow_on_url_authenticated_encounters=True)
    if not user.has_role(ROLE.PATIENT.value):
        abort(
            400,
            "only supported on patients."
            "  see also /api/staff/<id>/research_study")

    return jsonify(research_study=patient_research_study_status(user))


@research_study_api.route('/api/staff/<int:user_id>/research_study')
@crossdomain()
@oauth.require_oauth()
def rs_for_staff(user_id):
    """Returns simple JSON for research studies in staff user's domain

    ---
    tags:
      - User
      - ResearchStudy
    operationId: research_studies_for_staff
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
          Returns the list of research_studies the requested staff user is
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
        abort(
            400,
            "wrong request path for patient,"
            " see /api/patient/<int:user_id>/research_study")

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
        ResearchProtocol.research_study_id).order_by(
        ResearchProtocol.research_study_id).distinct()
    results = [
        ResearchStudy.query.get(s.research_study_id).as_fhir()
        for s in studies]

    return jsonify(research_study=results)
