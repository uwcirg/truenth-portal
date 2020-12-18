from flask import Blueprint, current_app, jsonify, request
from .empro_states import users_trigger_state
from .models import TriggerState
from ..views.crossdomain import crossdomain
from ..extensions import oauth
from ..models.user import get_user

trigger_states = Blueprint('trigger_states', __name__)


@trigger_states.route('/api/user/<int:user_id>/triggers')
@crossdomain()
@oauth.require_oauth()
def user_triggers(user_id):
    """Return a JSON object defining the current triggers for user

    Query string parameters supported for additional debugging:
    :param reprocess_qnr_id: ID for QNR (must belong to matching patient)
    :param purge: set True to purge observations and rerun through SDC

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

    ts = users_trigger_state(user_id)

    # Debugging parameter - reprocess as if given QNR was just submitted
    if request.args.get('reprocess_qnr_id'):
        from .empro_states import evaluate_triggers
        from ..models.questionnaire_response import QuestionnaireResponse
        qnr = QuestionnaireResponse.query.get(
            request.args.get('reprocess_qnr_id'))
        if qnr.subject_id != user_id:
            raise ValueError("QNR subject doesn't match requested user")

        if request.args.get("purge", '').lower() == 'true':
            from portal.tasks import extract_observations
            qnr.purge_related_observations()

            # reset state to allow processing
            ts = users_trigger_state(qnr.subject_id)
            current_app.logger.debug(
                f"triggers view: force transition from {ts.state} to 'due")
            ts.state = 'due'

            extract_observations(qnr.id)

        current_app.logger.debug(
            f"triggers view: evaluate_triggers() for {user_id} on request"
        )
        evaluate_triggers(qnr, override_state=True)
        ts = users_trigger_state(user_id)

    return jsonify(ts.as_json())


@trigger_states.route('/api/user/<int:user_id>/trigger_history')
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
