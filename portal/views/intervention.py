"""Intervention API view functions"""
from flask import abort, Blueprint, jsonify
from flask import current_app, request
from flask_user import roles_required
import json
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import Unauthorized

from ..audit import auditable_event
from ..models.auth import validate_client_origin
from ..models.group import Group, UserGroup
from ..models.intervention import INTERVENTION, UserIntervention
from ..models.message import EmailMessage
from ..models.user import current_user, User
from ..models.relationship import RELATIONSHIP
from ..models.role import ROLE
from ..extensions import oauth
from ..extensions import db
from ..models.intervention_strategies import AccessStrategy


intervention_api = Blueprint('intervention_api', __name__, url_prefix='/api')


@intervention_api.route(
    '/intervention/<string:intervention_name>/user/<int:user_id>')
@oauth.require_oauth()
def user_intervention_get(intervention_name, user_id):
    """Get settings for named user and intervention

    Returns JSON defining current settings for the given intervention
    and user_id, with only defined fields returned.

    ---
    operationId: user_intervention_get
    tags:
      - Intervention
    produces:
      - application/json
    parameters:
      - name: intervention_name
        in: path
        description: TrueNTH intervention_name
        required: true
        type: string
      - name: user_id
        in: path
        description: TrueNTH user identification
        required: true
        type: string
    responses:
      200:
        description: user intervention settings
        schema:
          id: intervention_access
          required:
            - user_id
          properties:
            user_id:
              type: string
              description:
                Truenth user identifier referring to whom the request applies
            access:
              type: string
              enum:
                - forbidden
                - granted
            card_html:
              type: string
              description:
                Custom HTML for display on intervention card for the
                referenced user
            link_label:
              type: string
              description:
                Custom text for display on the button or link within the card
                for the referenced user
            link_url:
              type: string
              description:
                Custom URL to use as the target for the button or link within
                the card for the referenced user
            status_text:
              type: string
              description:
                Custom text to display in the status column for the referenced
                user
            provider_html:
              type: string
              description:
                Custom HTML for display in patient list for care providers,
                as seen on the /patients view, specific to the referenced
                user..
      401:
        description:
          if missing valid OAuth SERVICE token or the service user owning
          the token isn't sponsored by the named intervention owner.
      404:
        description:
          if either the intervention name or the user_id given can't be found

    """
    intervention = getattr(INTERVENTION, intervention_name)
    if not intervention:
        abort (404, 'no such intervention {}'.format(intervention_name))
    current_user().check_role(permission='edit', other_id=user_id)

    ui = UserIntervention.query.filter_by(
        user_id=user_id, intervention_id=intervention.id).first()
    if not ui:
        ui = UserIntervention(user_id=user_id)
    return jsonify(ui.as_json())


@intervention_api.route('/intervention/<string:intervention_name>',
                        methods=('PUT',))
@oauth.require_oauth()
@roles_required(ROLE.SERVICE)
def user_intervention_set(intervention_name):
    """Update user access to the named intervention

    Submit a JSON doc with the user_id and other fields to set.  Keep
    in mind the PUT defines the whole resource for the user_id on the
    named intervention, calling GET first may be advisable.

    Only available as a service account API - the named intervention
    must be associated with the service account sponsor.

    NB - for `access`, interventions have a global 'public_access' setting.
    Only when public_access is unset are individual accounts consulted.

    ---
    operationId: user_intervention_set
    tags:
      - Intervention
    produces:
      - application/json
    parameters:
      - name: intervention_name
        in: path
        description: TrueNTH intervention_name
        required: true
        type: string
      - in: body
        name: body
        schema:
          id: intervention_access
          required:
            - user_id
          properties:
            user_id:
              type: string
              description:
                Truenth user identifier referring to whom the request applies
            access:
              type: string
              enum:
                - forbidden
                - granted
            card_html:
              type: string
              description:
                Custom HTML for display on intervention card for the
                referenced user
            link_label:
              type: string
              description:
                Custom text for display on the button or link within the card
                for the referenced user
            link_url:
              type: string
              description:
                Custom URL to use as the target for the button or link within
                the card for the referenced user.  The origin must validate
                to be within the list of known domains, including the
                application URL for this intervention
            status_text:
              type: string
              description:
                Custom text to display in the status column for the referenced
                user
            provider_html:
              type: string
              description:
                Custom HTML for display in patient list for care providers,
                as seen on the /patients view, specific to the referenced
                user
    responses:
      200:
        description: successful operation
        schema:
          id: response
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      401:
        description:
          if missing valid OAuth SERVICE token or the service user owning
          the token isn't sponsored by the named intervention owner.

    """
    intervention = getattr(INTERVENTION, intervention_name)
    if not intervention:
        abort (404, 'no such intervention {}'.format(intervention_name))

    # service account being used must belong to the intervention owner
    if not (intervention.client and intervention.client.user.has_relationship(
        relationship_name=RELATIONSHIP.SPONSOR, other_user=current_user())):
        abort(401, "Service account sponsored by intervention owner required")

    if not request.json or 'user_id' not in request.json:
        abort(400, "Requires JSON defining at least user_id")
    user_id = request.json.get('user_id')
    current_user().check_role(permission='edit', other_id=user_id)

    ui = UserIntervention.query.filter_by(
        user_id=user_id, intervention_id=intervention.id).first()
    if not ui:
        ui = UserIntervention(user_id=user_id,
                              intervention_id=intervention.id)
        db.session.add(ui)
    link = request.json.get('link_url')
    if link:
        try:
            validate_client_origin(link)
        except Unauthorized:
            abort(400, "link_url ill formed or origin not recognized")
        ui.link_url = link
    ui.access = request.json.get('access')
    ui.card_html = request.json.get('card_html')
    ui.link_label = request.json.get('link_label')
    ui.status_text = request.json.get('status_text')
    ui.provider_html = request.json.get('provider_html')
    db.session.commit()
    auditable_event("updated {0} using: {1}".format(
        intervention.description, json.dumps(request.json)),
        user_id=current_user().id)
    return jsonify(message='ok')


@intervention_api.route(
    '/intervention/<string:intervention_name>/access_rule')
@oauth.require_oauth()
@roles_required(ROLE.ADMIN)
def intervention_rule_list(intervention_name):
    """Return the list of intervention rules for named intervention

    NB - not documenting in swagger at this time, intended for internal use
    only.  See ``http://truenth-shared-services.readthedocs.io/en/latest/interventions.html#access``

    """
    intervention = getattr(INTERVENTION, intervention_name)
    if not intervention:
        abort (404, 'no such intervention {}'.format(intervention_name))
    rules = [x.as_json() for x in intervention.access_strategies]
    return jsonify(rules=rules)


@intervention_api.route(
    '/intervention/<string:intervention_name>/access_rule', methods=('POST',))
@oauth.require_oauth()
@roles_required([ROLE.ADMIN, ROLE.SERVICE])
def intervention_rule_set(intervention_name):
    """POST an access rule to the named intervention

    Submit a JSON doc with the access strategy details to include
    for the named intervention.

    Only available as a service account API - the named intervention
    must be associated with the service account sponsor.

    NB - interventions have a global 'public_access' setting.  Only
    when unset are access rules consulted.

    NB - not documenting in swagger at this time, intended for internal use
    only.  See ``http://truenth-shared-services.readthedocs.io/en/latest/interventions.html#access``

    """
    intervention = getattr(INTERVENTION, intervention_name)
    if not intervention:
        abort (404, 'no such intervention {}'.format(intervention_name))

    if not request.json or 'function_details' not in request.json:
        abort(400, "Requires JSON with well defined access strategy")
    access_strategy = AccessStrategy.from_json(request.json)
    intervention.access_strategies.append(access_strategy)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, "`rank` values must be unique per intervention")

    auditable_event("added {} to intervention {}".format(
        access_strategy, intervention.description), user_id=current_user().id)
    return jsonify(message='ok')


@intervention_api.route(
    '/intervention/<string:intervention_name>/communicate', methods=('POST',))
@oauth.require_oauth()
def intervention_communicate(intervention_name):
    """POST a message or trigger communication as detailed

    Submit JSON describing communication details, such as the group
    of users to contact, sending protocol and message

    ---
    operationId: intervention_communicate
    tags:
      - Intervention
    produces:
      - application/json
    parameters:
      - name: intervention_name
        in: path
        description: TrueNTH intervention_name
        required: true
        type: string
      - in: body
        name: body
        schema:
          id: message_details
          required:
            - group_name
            - protocol
            - subject
            - message
          properties:
            group_name:
              type: string
              description:
                Truenth group name referring to whom to include as recipients.
                See `/api/group/` for options.
            protocol:
              type: string
              enum:
                - email
            subject:
              type: string
              description:
                Text subject of message, limited to 78 characters in length.
            message:
              type: string
              description: Text or HTML to transmit as the message body.
    responses:
      200:
        description: successful operation
        schema:
          id: response
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "sent"
      401:
        description:
          if missing valid OAuth SERVICE token or the service user owning
          the token isn't sponsored by the named intervention owner.
      404:
        description: if the named intervention doesn't exist

    """
    intervention = getattr(INTERVENTION, intervention_name)
    if not intervention:
        abort (404, 'no such intervention {}'.format(intervention_name))

    if not request.json:
        abort(400, "Requires JSON detailing communication")

    group = Group.query.filter_by(name=request.json.get('group_name')).first()
    if not group:
        abort(400, "JSON requires a valid `group_name`")

    if 'email' != request.json.get('protocol'):
        abort(400, "Only protocol of email is supported at this time")

    subject = request.json.get('subject')
    if not subject or  len(subject) > 78:
        abort(400,
              "`subject` is required and limited to 78 characters in length")

    recipients = [
        u.email for u in User.query.join(UserGroup).filter(
            UserGroup.group_id==group.id)]
    if not recipients:
        abort(400, "no recipients found")

    sender = current_app.config['MAIL_DEFAULT_SENDER']
    email = EmailMessage(subject=subject, body=request.json.get('message'),
            recipients=' '.join(recipients), sender=sender,
            user_id=current_user().id)
    email.send_message()

    db.session.add(email)
    db.session.commit()
    auditable_event("intervention {} sent {}".format(
        intervention.description, email), user_id=current_user().id)
    return jsonify(message='sent')
