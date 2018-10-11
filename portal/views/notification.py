"""Views for UserNotifications"""
from flask import Blueprint, abort, current_app, jsonify

from ..database import db
from ..extensions import oauth
from ..models.notification import UserNotification
from ..models.user import current_user, get_user, get_user_or_abort
from ..type_tools import check_int
from .crossdomain import crossdomain

notification_api = Blueprint('notification_api', __name__, url_prefix='/api')


@notification_api.route(
    '/user/<int:user_id>/notification',
    methods=('OPTIONS', 'GET'))
@crossdomain()
@oauth.require_oauth()
def get_user_notification(user_id):
    """Retrieve Notifications for the given User
    ---
    tags:
      - Notification
      - User
    operationId: getUserNotification
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
        description: successful operation
        schema:
          id: user_notifications
          properties:
            notifications:
              type: array
              items:
                type: object
                required:
                  - id
                  - resourceType
                  - name
                  - content
                  - created_at
                properties:
                  id:
                    type: integer
                    format: int64
                    description: identifier for the Notification
                  resourceType:
                    type: string
                    description: JSON object resource type
                  name:
                    type: string
                    description: identifying name of the Notification
                  content:
                    type: string
                    description: content to be displayed
                  created_at:
                    type: string
                    description:
                      original UTC date-time of the Notification creation
      400:
        description: if the request includes invalid data
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to edit requested user_id
      404:
        description: if user_id don't exist
    security:
      - ServiceToken: []

    """
    check_int(user_id)

    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='edit', other_id=user_id)
        user = get_user_or_abort(user_id)
    notifs = [notif.as_json() for notif in user.notifications]

    return jsonify(notifications=notifs)


@notification_api.route(
    '/user/<int:user_id>/notification/<int:notification_id>',
    methods=('OPTIONS', 'DELETE'))
@crossdomain()
@oauth.require_oauth()
def delete_user_notification(user_id, notification_id):
    """Remove the corresponding UserNotification for given User & Notification
    ---
    tags:
      - Notification
      - User
    operationId: deleteUserNotification
    parameters:
      - name: user_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - name: notification_id
        in: path
        description: General Notification ID
        required: true
        type: integer
        format: int64
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: response_ok
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      400:
        description: if the request includes invalid data
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to edit requested user_id
      404:
        description: if user_id or notification_id don't exist
    security:
      - ServiceToken: []

    """
    current_app.logger.debug(
        'delete user notification called for user {} and '
        'notification {}'.format(user_id, notification_id))

    check_int(user_id)
    check_int(notification_id)

    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='edit', other_id=user_id)
        user = get_user(user_id)
    if user.deleted:
        abort(400, "deleted user - operation not permitted")

    un = UserNotification.query.filter_by(
        user_id=user_id, notification_id=notification_id).first()
    if not un:
        abort(404, 'notification {} not found for '
                   'user {}'.format(user_id, notification_id))

    db.session.delete(un)
    db.session.commit()

    return jsonify(message="ok")
