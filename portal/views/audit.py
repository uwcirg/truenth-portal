"""Views for audit"""
from flask import Blueprint, jsonify
from flask_user import roles_required
from sqlalchemy import or_

from ..extensions import oauth
from ..models.audit import Audit
from ..models.role import ROLE
from ..models.user import get_user
from .crossdomain import crossdomain

audit_api = Blueprint('audit_api', __name__, url_prefix='/api')


@audit_api.route('/user/<int:user_id>/audit')
@crossdomain()
@roles_required(
    [ROLE.ADMIN.value, ROLE.STAFF_ADMIN.value, ROLE.STAFF.value,
     ROLE.INTERVENTION_STAFF.value])
@oauth.require_oauth()
def get_audit(user_id):
    """Access audit info for given user

    Returns array of audit data for requested user.

    Only available for admins
    ---
    tags:
      - Audit
    operationId: get_audit
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
        description:
          Returns array of audit data for user.
        schema:
          id: audits
          required:
            - by
            - lastUpdated
            - version
          properties:
            by:
              type: object
              description: A reference from one resource to another
              properties:
                reference:
                  type: string
                  externalDocs:
                    url: http://hl7.org/implement/standards/fhir/DSTU2/references-definitions.html#Reference.reference
              type: string
              description:
                Reference to user who generated the auditable event
            comment:
              type: string
              description:
                Details of the audit event, if available
            lastUpdated:
              type: string
              description: UTC timestamp capturing when audit occurred
            version:
              type: string
              description: software version when audit took place
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """
    user = get_user(user_id, 'view')
    audits = Audit.query.filter(or_(
        Audit.user_id == user.id,
        Audit.subject_id == user.id))
    results = [audit.as_fhir() for audit in audits]
    return jsonify(audits=results)
