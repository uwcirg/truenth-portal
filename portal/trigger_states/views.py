from flask import Blueprint, jsonify, request
from .empro_states import users_trigger_state
from ..views.crossdomain import crossdomain
from ..extensions import oauth
from ..models.user import get_user

trigger_states = Blueprint('trigger_states', __name__)


@trigger_states.route('/api/user/<int:user_id>/triggers')
@crossdomain()
@oauth.require_oauth()
def user_triggers(user_id):
    """Return a JSON object defining the current triggers for user

    :returns TriggerState: with ``state`` attribute meaning:
      - unstarted: no info avail for user
      - due: users triggers unavailable; assessment due
      - inprocess: triggers are not ready; continue to poll for results
      - processes: triggers available in TriggerState.triggers attribute

    """
    # confirm view access
    get_user(user_id, 'view')

    ts = users_trigger_state(user_id)

    # Debugging parameter - reprocess as if given QNR was just submitted
    if request.args.get('reprocess_qnr_id'):
        from .empro_states import evaluate_triggers
        from ..models.questionnaire_response import QuestionnaireResponse
        qnr = QuestionnaireResponse.query.get(
            request.args.get('reprocess_qnr_id'))
        if qnr.subject_id != user_id:
            raise ValueError("QNR subject doesn't match requested user")
        evaluate_triggers(qnr, override_state=True)
        ts = users_trigger_state(user_id)

    return jsonify(ts.as_json())
