from flask import Blueprint, abort, jsonify, make_response, request
from flask_user import roles_required

from .empro_states import extract_observations, users_trigger_state
from .models import TriggerState
from ..database import db
from ..extensions import oauth
from ..models.role import ROLE
from ..models.user import get_user
from ..views.crossdomain import crossdomain

trigger_states = Blueprint('trigger_states', __name__)


@trigger_states.route('/api/questionnaire_response/<int:qnr_id>/$rescore')
@roles_required([ROLE.ADMIN.value])
@oauth.require_oauth()
def rescore_qnr(qnr_id):
    """Backdoor to force a re-score of a questionnaire_response out of band.

    Typically, a questionnaire response is scored (via SDC) when it is POSTed
    to the system.  In the event of an exceptional state where one didn't
    finish or get processed, this API will re-trigger the process.

    NB, it is expected the user's most recent trigger state is stuck in
    an `inprocess` state.  Exception will be raised if found to be otherwise.

    :param qnr_id:  the questionnaire_response id to re-score.
    :return: "success"
    """
    try:
        extract_observations(
            questionnaire_response_id=qnr_id, override_state=True)
    except (AttributeError, ValueError) as err:
        return make_response(f"ERROR: {err}", 500)
    return make_response("success", 200)


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


@trigger_states.route('/api/patient/<int:user_id>/triggers/opt_out', methods=['POST', 'PUT'])
@crossdomain()
@oauth.require_oauth()
def opt_out(user_id):
    """Takes a JSON object defining the domains for which to opt-out

    The ad-hoc JSON expected resembles that returned from `user_triggers()`
    simplified to only interpret the domains for which the user chooses to
    opt-out.

    :returns: TriggerState in JSON for the requested visit month
    """
    get_user(user_id, 'edit', allow_on_url_authenticated_encounters=True)
    ts = users_trigger_state(user_id)
    try:
        ts = ts.apply_opt_out(request.json)
    except ValueError as e:
        abort(400, str(e))

    # persist the change
    db.session.commit()
    return jsonify(ts.as_json())


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
