"""Patient API - implements patient specific views such as patient search

NB - this is not to be confused with 'patients', which defines views
for providers

"""
from flask import abort, Blueprint, request
from werkzeug.exceptions import Unauthorized

from ..audit import auditable_event
from .demographics import demographics
from ..extensions import oauth
from ..models.role import ROLE
from ..models.user import current_user, User


patient_api = Blueprint('patient_api', __name__, url_prefix='/api/patient')


@patient_api.route('/')
@oauth.require_oauth()
def patient_search():
    """Looks up patient from given parameters, returns FHIR Patient if found

    Takes key=value pairs to look up.  At this time, only email is supported.

    Example search:
        /api/patient?email=username@server.com

    Returns a FHIR patient resource (http://www.hl7.org/fhir/patient.html)
    formatted in JSON if a match is found, 404 otherwise.

    NB - the results are restricted to users with the patient role.  It is
    therefore possible to get no results from this and still see a unique email
    collision from existing non-patient users.

    ---
    tags:
      - Patient
    operationId: patient_search
    produces:
      - application/json
    parameters:
      - name: search_parameters
        in: query
        description: Search parameters, such as `email`
        required: true
        type: string
    responses:
      200:
        description:
          Returns FHIR patient resource (http://www.hl7.org/fhir/patient.html)
          in JSON if a match is found.  Otherwise responds with a 404 status
          code.
      401:
        description:
          if missing valid OAuth token
      404:
        description:
          if there is no match found, or the user lacks permission to look
          up details on the match.

    """
    ## search criteria - only email used at this time
    search_params = {}
    for k,v in request.args.items():
        if k == 'email':
            search_params[k] = v
        else:
            abort(400, "can't search on '{}' at this time".format(k))

    match = User.query.filter_by(**search_params)
    if match.count() > 1:
        abort(400, "can't yet bundle results, multiple found")
    if match.count() == 1:
        user = match.one()
        try:
            current_user().check_role(permission='view', other_id=user.id)
            if user.has_role(ROLE.PATIENT):
                return demographics(patient_id=user.id)
        except Unauthorized:
            # Mask unauthorized as a not-found.  Don't want unauthed users
            # farming information
            auditable_event("looking up users with inadequate permission",
                            user_id=current_user().id)
            abort(404)
    abort(404)
