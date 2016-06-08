from flask import abort, current_app, jsonify, url_for
from flask import Blueprint, render_template, request
from werkzeug.exceptions import Unauthorized

from ..extensions import oauth
from ..models.auth import validate_client_origin
from ..models.user import current_user


coredata_api = Blueprint('coredata_api', __name__, url_prefix='/api/coredata')

OPTIONS = ('ethnicity', 'procedure', 'race')

@coredata_api.route('/options', methods=('GET',))
def options():
    return jsonify(require_options=OPTIONS)


@coredata_api.route('/acquire', methods=('GET',))
@oauth.require_oauth()
def acquire():
    """Redirection target to acquire coredata from the user

    Clients (interventions) that require core data not yet entered
    by a patient, may redirect the patients user agent to this endpoint
    including one or more 'require' parameters for the data point(s)
    to obtain.  Call `GET /api/coredata/options` for available options.

    The user-agent will be redirected back to the client's site using
    the given 'next' parameter value, required to be urlencoded.  Any
    query string parameters on the next url will be included in the redirect.

    Clients are expected to repeat the request to obtain any entered data
    after the redirect occurs.  For example, if procedure data is
    required, another call to `/patient/<patient_id>/procedure` will return
    any new procedure data acquired as well as existing.

    ---
    tags:
      - Coredata
    operationId: acquire
    produces:
      - text/html
    parameters:
      - name: next
        in: query
        description:
            Return address for user-agent redirection once complete, must
            be urlencoded.  May include additional parameters for the client's
            use.  NB - the origin of the next url must validate as belonging
            to a configured client intervention.
        required: true
        type: string
      - name: require
        in: query
        description:
            Data to acquire.  Multiple `require` parameters may be included
            to present the user with multiple forms for respective data
            collection.
        required: true
        type: string
    responses:
      302:
        description:
          After user interacts with form and submits, the user-agent
          will be redirected back to the given 'next' parameter.
      400:
        description:
          if no `require` parameter is sent or the value isn't recognized as an
          available option.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
      403:
        description: if the next parameter origin is not recognized

    """
    # Require and maintain a valid return address
    return_address = request.args.get('next')
    try:
        validate_client_origin(return_address)
    except Unauthorized:
        current_app.logger.warning("Unauthorized return address %s",
                                   return_address)
        abort(403, "Required `next` parameter not a valid origin")

    require = request.args.getlist('require')
    for r in require:
        if r not in OPTIONS:
            abort(400, "Unknown value for require '{}' -- see {}".format(
                r, url_for('coredata_api.options', _external=True)))

    return render_template("coredata.html", user=current_user(),
        require=require, return_address=return_address)
