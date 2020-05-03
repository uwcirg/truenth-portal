from flask import Blueprint, abort, jsonify, request

from ..extensions import oauth
from ..models.identifier import Identifier
from ..models.questionnaire_bank import Questionnaire, QuestionnaireBank
from ..system_uri import TRUENTH_QUESTIONNAIRE_CODE_SYSTEM
from .crossdomain import crossdomain

questionnaire_api = Blueprint('questionnaire_api', __name__)


@questionnaire_api.route('/api/questionnaire_bank')
@crossdomain()
@oauth.require_oauth()
def questionnaire_bank_list():
    """Obtain a bundle (list) of all QuestionnaireBanks

    ---
    operationId: questionnaire_bank_list
    tags:
      - Assessment Engine
    produces:
      - application/json
    responses:
      200:
        description: return current list of questionnaire banks
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    bundle = QuestionnaireBank.generate_bundle()
    return jsonify(bundle)


@questionnaire_api.route('/api/questionnaire')
@crossdomain()
def questionnaire_list():
    """Obtain a bundle (list) of all Questionnaires

    ---
    operationId: questionnaire_list
    tags:
      - Assessment Engine
    produces:
      - application/json
    responses:
      200:
        description: return current list of questionnaires
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    bundle = Questionnaire.generate_bundle()
    return jsonify(bundle)


@questionnaire_api.route('/api/questionnaire/<string:value>')
@crossdomain()
def get_questionnaire(value):
    """Return the specified Questionnaire

    ---
    operationId: get_questionnaire
    tags:
      - Assessment Engine
    parameters:
      - name: value
        in: path
        description: Questionnaire name, i.e. value portion of identifier
        required: true
        type: string
      - name: system
        in: query
        description: Identifier system
        required: true
        type: string
    produces:
      - application/json
    responses:
      200:
        description: return specified questionnaire
      400:
        description: missing or invalid questionnaire name
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    try:
        value = str(value)
    except ValueError:
        abort(400, "invalid input '{}' - must be a valid string".format(value))

    # Tight constraint, but only supporting a single system at this time
    system = request.args.get('system')
    if system != TRUENTH_QUESTIONNAIRE_CODE_SYSTEM:
        abort(
            404,
            "Not found, check system value - expected `{}`".format(
                TRUENTH_QUESTIONNAIRE_CODE_SYSTEM))
    ident = Identifier(_value=value, system=system).add_if_not_found()
    q = Questionnaire.find_by_identifier(identifier=ident)
    return jsonify(q.as_fhir())
