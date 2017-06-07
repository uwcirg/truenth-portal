"""Views for Terms Of Use"""
from flask import abort, jsonify, Blueprint, request
from re import sub
from sqlalchemy import and_
from sqlalchemy.exc import DataError

from ..database import db
from ..extensions import oauth
from ..models.app_text import app_text, InitialConsent_ATMA, VersionedResource
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
          Returns URL for current Terms Of Use, with respect to current
          system configuration in simple json {url:"http..."}

    """
    terms = VersionedResource(app_text(InitialConsent_ATMA.name_key()))
    return jsonify(url=terms.url)


@tou_api.route('/user/<int:user_id>/tou')
@oauth.require_oauth()
def get_tou(user_id):
    """Access all Terms Of Use info for given user

    Returns ToU json for requested user.
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
    produces:
      - application/json
    responses:
      200:
        description:
          Returns the list of ToU agreements for the requested user.
        schema:
          id: tous
          properties:
            tou_agreements:
              type: array
              items:
                type: object
                required:
                  - agreement_url
                  - type
                properties:
                  agreement_url:
                    type: string
                    description: URL pointing to agreement text
                  type:
                    type: string
                    description:
                      Type of ToU agreement (privacy policy, website ToU, etc.)
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    user = get_user(user_id)
    if not user:
        abort(404)
    current_user().check_role(permission='view', other_id=user_id)

    tous = ToU.query.join(Audit).filter(Audit.user_id == user_id)

    return jsonify(tous=[d.as_json() for d in tous])


@tou_api.route('/user/<int:user_id>/tou/<string:tou_type>')
@oauth.require_oauth()
def get_tou_by_type(user_id, tou_type):
    """Access Terms Of Use info for given user & ToU type

    Returns ToU{'accepted': true|false} for requested user given the
    specified ToU type.
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
      - name: tou_type
        in: path
        description: ToU type
        required: true
        type: string
    responses:
      200:
        description:
          Returns 'accepted' True or False for requested user & ToU type.
      400:
        description:
          if the given type string does not match a valid ToU type
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    user = get_user(user_id)
    if not user:
        abort(404)
    current_user().check_role(permission='view', other_id=user_id)

    tou_type = sub('-',' ',tou_type)

    try:
        tous = ToU.query.join(Audit).filter(and_(Audit.user_id == user_id,
                                            ToU.type == tou_type)).first()
    except DataError:
        abort(400, 'invalid tou type')

    if tous:
        return jsonify(accepted=True)
    return jsonify(accepted=False)


@tou_api.route('/user/<user_id>/tou/accepted', methods=('POST',))
@oauth.require_oauth()
def post_user_accepted_tou(user_id):
    """Accept Terms Of Use on behalf of user

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
              description: URL for Terms Of Use text
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
    audit = Audit(user_id = authd_user.id, subject_id=user_id,
                  comment = "user {} posting accepted ToU for user {}".format(
                      authd_user.id, user_id), context='tou')
    db.session.add(audit)
    return accept_tou(user_id)


@tou_api.route('/tou/accepted', methods=('POST',))
@oauth.require_oauth()
def accept_tou(user_id=None):
    """Accept Terms Of Use info for authenticated user

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
              description: URL for Terms Of Use text
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
    audit = Audit(user_id = user.id, subject_id=user.id,
        comment = "ToU accepted", context='tou')
    tou_type = request.json.get('type') or 'website terms of use'
    tou = ToU(audit=audit, agreement_url=request.json['agreement_url'],
              type=tou_type)
    db.session.add(tou)
    db.session.commit()
    # Note: skipping auditable_event, as there's a audit row created above
    return jsonify(message="accepted")
