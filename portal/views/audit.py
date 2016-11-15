"""Views for audit"""
from flask import abort, jsonify, Blueprint
from flask_user import roles_required
from sqlalchemy import or_

from ..extensions import oauth
from ..models.audit import Audit
from ..models.user import current_user, get_user
from ..models.role import ROLE


audit_api = Blueprint('audit_api', __name__, url_prefix='/api')

@audit_api.route('/user/<int:user_id>/audit')
@roles_required([ROLE.ADMIN, ROLE.PROVIDER])
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

    """
    user = get_user(user_id)
    if not user:
        abort(404)
    current_user().check_role(permission='view', other_id=user_id)
    audits = Audit.query.filter(or_(
        Audit.user_id==user_id,
        Audit.comment.like('%on user {}%'.format(user_id))))
    results = [audit.as_fhir() for audit in audits]
    return jsonify(audits=results)
