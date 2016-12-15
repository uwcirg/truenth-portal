"""Views for Terms of Use"""
from flask import abort, jsonify, Blueprint, request

from ..extensions import db, oauth
from ..models.app_text import app_text, ToU_ATMA, VersionedResource
from ..models.audit import Audit
from ..models.user import current_user, get_user
from ..models.tou import ToU


tou_api = Blueprint('tou_api', __name__, url_prefix='/api')


@tou_api.route('/tou')
def get_current_tou_url():
    """Return current ToU URL

    ---
    tags:
      - Terms Of Use
    operationId: getCurrentToU
    produces:
      - application/json
    responses:
      200:
        description:
          Returns URL for current Terms of Use, with respect to current
          system configuration in simple json {url:"http..."}

    """
    _, url = VersionedResource.fetch_elements(app_text(ToU_ATMA.name_key()))
    return jsonify(url=url)


@tou_api.route('/user/<int:user_id>/tou')
@oauth.require_oauth()
def get_tou(user_id):
    """Access Terms of Use info for given user

    Returns ToU{'accepted': true|false} for requested user.
    ---
    tags:
      - Terms Of Use
    operationId: getToU
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
          Returns 'accepted' True or False for requested user.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    user = get_user(user_id)
    if not user:
        abort(404)
    current_user().check_role(permission='view', other_id=user_id)
    tous = ToU.query.join(Audit).filter(Audit.user_id==user_id).first()
    if tous:
        return jsonify(accepted=True)
    return jsonify(accepted=False)


@tou_api.route('/user/<user_id>/tou/accepted', methods=('POST',))
@oauth.require_oauth()
def post_user_accepted_tou(user_id):
    """Accept Terms of Use on behalf of user

    POST simple JSON describing ToU the user accepted for persistence.  This
    endpoint enables service or other users to set accepted ToU on behalf of
    any user they have permission to edit.

    ---
    tags:
      - Terms Of Use
    operationId: userAcceptToU
    produces:
      - application/json
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - name: body
        in: body
        schema:
          id: acceptedToU
          description: Details of accepted ToU
          required:
            - agreement_url
          properties:
            agreement_url:
              description: URL for Terms of Use text
              type: string
    responses:
      200:
        description: message detailing success
      400:
        description: if the required JSON is ill formed
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to edit requested user

    """
    authd_user = current_user()
    authd_user.check_role(permission='edit', other_id=user_id)
    audit = Audit(user_id = authd_user.id,
                  comment = "user {} posting accepted ToU for user {}".format(
                      authd_user.id, user_id))
    db.session.add(audit)
    return accept_tou(user_id)


@tou_api.route('/tou/accepted', methods=('POST',))
@oauth.require_oauth()
def accept_tou(user_id=None):
    """Accept Terms of Use info for authenticated user

    POST simple JSON describing ToU the user accepted for persistence.

    ---
    tags:
      - Terms Of Use
    operationId: acceptToU
    produces:
      - application/json
    parameters:
      - name: body
        in: body
        schema:
          id: acceptedToU
          description: Details of accepted ToU
          required:
            - agreement_url
          properties:
            agreement_url:
              description: URL for Terms of Use text
              type: string
    responses:
      200:
        description: message detailing success
      400:
        description: if the required JSON is ill formed
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to edit requested user

    """
    if user_id:
        user=get_user(user_id)
    else:
        user = current_user()
    if not request.json or 'agreement_url' not in request.json:
        abort(400, "Requires JSON with the ToU 'agreement_url'")
    audit = Audit(user_id = user.id, comment = "ToU accepted")
    tou = ToU(audit=audit, agreement_url=request.json['agreement_url'])
    db.session.add(tou)
    db.session.commit()
    # Note: skipping auditable_event, as there's a audit row created above
    return jsonify(message="accepted")
