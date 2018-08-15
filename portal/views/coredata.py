from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402

from urllib.parse import parse_qsl, urlencode, urlparse

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    url_for,
)
from werkzeug.exceptions import Unauthorized

from ..extensions import oauth
from ..models.client import validate_origin
from ..models.coredata import Coredata
from ..models.user import current_user, get_user_or_abort

coredata_api = Blueprint('coredata_api', __name__, url_prefix='/api/coredata')

OPTIONS = ('ethnicity', 'procedure', 'race')


@coredata_api.route('/options', methods=('GET',))
def options():
    return jsonify(require_options=OPTIONS)


def validate_request_args(request):
    """Validate values and return dict or raise exception

    Several endpoints take the same query string parameters.  Validate
    the values received and return in a dictionary if legit, or raise
    descriptive exception.

    """
    d = {}
    if request.args:
        for k in request.args.keys():
            if k == 'entry_method':
                accepted = ('paper', 'interview assisted')
                v = request.args.get(k)
                if v not in accepted:
                    abort(400, '{} value `{}` not in {}'.format(
                        k, v, accepted))
                d[k] = v
            else:
                abort(400, 'unsupported query param {}'.format(k))
    return d


@coredata_api.route('/user/<int:user_id>/still_needed', methods=('GET',))
@oauth.require_oauth()
def still_needed(user_id):
    """Looks up missing coredata elements for given user

    :param entry_method: optional query string parameter used to define entry
        method.  Useful from front end when in `enter manually` to
        differentiate `enter manually - paper` from
        `enter manually - interview assisted`

    :returns: simple JSON struct with a list (potentially empty) of the
        coredata elements still needed as 'field' elements, with an optional
        'collection_method' defined if needed.

    """
    current_user().check_role(permission='view', other_id=user_id)
    user = get_user_or_abort(user_id)
    needed = Coredata().still_needed(user, **validate_request_args(request))
    return jsonify(still_needed=needed)


@coredata_api.route('/user/<int:user_id>/required', methods=('GET',))
@oauth.require_oauth()
def requried(user_id):
    """Looks up required core data elements for user

    :param entry_method: optional query string parameter used to define entry
        method.  Useful from front end when in `enter manually` to
        differentiate `enter manually - paper` from
        `enter manually - interview assisted`

    :returns: simple JSON struct with a list of the coredata elements
        required for the given user.  The list is dependent on the application
        configuration and details such as user's role, organizations and
        intervention affiliations.

    """
    current_user().check_role(permission='view', other_id=user_id)
    user = get_user_or_abort(user_id)
    required = Coredata().required(user, **validate_request_args(request))
    return jsonify(required=required)


@coredata_api.route('/user/<int:user_id>/optional', methods=('GET',))
@oauth.require_oauth()
def optional(user_id):
    """Looks up optional core data elements for user

    :param entry_method: optional query string parameter used to define entry
        method.  Useful from front end when in `enter manually` to
        differentiate `enter manually - paper` from
        `enter manually - interview assisted`

    :returns: simple JSON struct with a list of the coredata elements
        optional for the given user.  The list is dependent on the application
        configuration and details such as user's role, organizations and
        intervention affiliations.

    """
    current_user().check_role(permission='view', other_id=user_id)
    user = get_user_or_abort(user_id)
    results = Coredata().optional(user, **validate_request_args(request))
    return jsonify(optional=results)


@coredata_api.route('/acquire', methods=('GET',))
@oauth.require_oauth()
def acquire():
    """Redirection target to acquire coredata from the user

    Clients (interventions) that require core data not yet entered
    by a patient, may redirect the patient's user agent to this endpoint
    including one or more 'require' parameters for the data point(s)
    to obtain.  `GET /api/coredata/options` returns available options.

    The user-agent will be redirected back to the client's site using
    the given 'next' parameter value, required to be urlencoded.  Any
    query string parameters on the next url will be included in the redirect.

    Clients are expected to repeat the request to obtain any entered data
    after the redirect occurs.  For example, if procedure data is
    required, another call to `/patient/<patient_id>/procedure` will return
    any new procedure data acquired as well as existing.

    NB: providing multiple values for the `require` parameter is supported,
    with the parameter repeated as in `?require=first&require=second` (Note,
    the ampersand should **not** be quoted)

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
        validate_origin(return_address)
    except Unauthorized:
        current_app.logger.warning("Unauthorized return address %s",
                                   return_address)
        abort(403, "Required `next` parameter not a valid origin")

    require = request.args.getlist('require')
    for r in require:
        if r not in OPTIONS:
            abort(400, "Unknown value for require '{}' -- see {}".format(
                r, url_for('coredata_api.options', _external=True)))

    def clean_return_address(return_address):
        """ Clean up the return address encoding if necessary

        URL encoding is necessary on contained parameters or it'll break the JS
        redirect in the template.  For example, if the return address contains
        an unquoted double quote, the JS function call to
        window.location.replace sees a different set of arguments

        :returns: the cleaned URL
        """
        url = return_address
        parsed = urlparse(return_address)
        qs = parse_qsl(parsed.query)
        if qs:
            url = (
                "{0.scheme}://{0.netloc}{0.path}?".format(parsed) +
                urlencode(qs))
        return url

    return render_template(
        "coredata.html", user=current_user(),
        require=require, return_address=clean_return_address(return_address))
