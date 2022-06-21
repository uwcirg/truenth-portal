from flask import Blueprint, jsonify
from .empro_states import users_trigger_state
from .models import TriggerState
from ..extensions import oauth
from ..models.user import get_user
from ..views.crossdomain import crossdomain

trigger_states = Blueprint('trigger_states', __name__)


@trigger_states.route('/api/patient/<int:user_id>/triggers')
@crossdomain()
@oauth.require_oauth()
def user_triggers(user_id):
    """Return a JSON object defining the current triggers for user

    :returns TriggerState: with ``state`` attribute meaning:
      - unstarted: no info avail for user
      - due: users triggers unavailable; assessment due
      - inprocess: triggers are not ready; continue to poll for results
      - processed: triggers available in TriggerState.triggers attribute
      - triggered: action taken on triggers (such as emails sent).
        ``triggers`` available as are ``triggers.actions``.
      - resolved: all actions completed (such as post-intervention QB taken)
        ``triggers`` available as are ``triggers.actions``.

    """
    # confirm view access
    get_user(user_id, 'view', allow_on_url_authenticated_encounters=True)
    return jsonify(users_trigger_state(user_id).as_json())


@trigger_states.route('/api/patient/<int:user_id>/trigger_history')
@crossdomain()
@oauth.require_oauth()
def user_trigger_history(user_id):
    """Return a JSON list of user's historical trigger records

    Returns ordered list (oldest to newest) of a user's trigger
    state history.

    :returns list of TriggerStates: with ``state`` attribute meaning:
      - unstarted: no info avail for user
      - due: users triggers unavailable; assessment due
      - inprocess: triggers are not ready; continue to poll for results
      - processed: triggers available in TriggerState.triggers attribute
      - triggered: action taken on triggers (such as emails sent).
        ``triggers`` available as are ``triggers.actions``.
      - resolved: all actions completed (such as post-intervention QB taken)
        ``triggers`` available as are ``triggers.actions``.

    """
    # confirm view access
    get_user(user_id, 'view')

    history = TriggerState.query.filter(
        TriggerState.user_id == user_id).order_by(TriggerState.id)
    results = [ts.as_json() for ts in history]
    return jsonify(results)
