"""Patient API - implements patient specific views such as patient search

NB - this is not to be confused with 'patients', which defines views
for staff

"""
import json

from flask import Blueprint, abort, jsonify, request
from sqlalchemy import and_
from werkzeug.exceptions import Unauthorized

from ..audit import auditable_event
from ..database import db
from ..extensions import oauth
from ..models.identifier import Identifier, UserIdentifier
from ..models.role import ROLE
from ..models.user import User, current_user, get_user_or_abort
from .demographics import demographics

patient_api = Blueprint('patient_api', __name__)


@patient_api.route('/api/patient/')
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
        description:
            Search parameters, such as `email` or `identifier`.  For
            identifier, URL-encode a serialized JSON object with the `system`
            and `value` attributes defined.  An example looking up a patient
            by a fake identifier
            `api/patient/?identifier={"system":%20"http://fake.org/id",%20"value":%20"12a7"}`
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
    search_params = {}
    for k, v in request.args.items():
        if k == 'email':
            search_params[k] = v
        elif k == 'identifier':
            try:
                ident_dict = json.loads(v)
                if not (ident_dict.get('system') and ident_dict.get('value')):
                    abort(400,
                          "need 'system' and 'value' to look up identifier")
                ui = UserIdentifier.query.join(
                    Identifier).filter(and_(
                        UserIdentifier.identifier_id == Identifier.id,
                        Identifier.system == ident_dict['system'],
                        Identifier._value == ident_dict['value'])).first()
                if ui:
                    search_params['id'] = ui.user_id
            except ValueError:
                abort(400, "Ill formed identifier parameter")
        else:
            abort(400, "can't search on '{}' at this time".format(k))

    if not search_params:
        # Nothing found worth looking up above
        abort(404)
    match = User.query.filter_by(**search_params)
    if match.count() > 1:
        abort(400, "can't yet bundle results, multiple found")
    if match.count() == 1:
        user = match.one()
        try:
            current_user().check_role(permission='view', other_id=user.id)
            if user.has_role(ROLE.PATIENT.value):
                return demographics(patient_id=user.id)
        except Unauthorized:
            # Mask unauthorized as a not-found.  Don't want unauthed users
            # farming information
            auditable_event("looking up users with inadequate permission",
                            user_id=current_user().id, subject_id=user.id,
                            context='authentication')
            abort(404)
    abort(404)


@patient_api.route('/api/patient/<int:patient_id>/deceased', methods=('POST',))
@oauth.require_oauth()
def post_patient_deceased(patient_id):
    """POST deceased datetime or status for a patient

    This convenience API wraps the ability to set a patient's
    deceased status and deceased date time - generally the /api/demographics
    API should be preferred.

    ---
    operationId: deceased
    tags:
      - Patient
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: deceased_details
          properties:
            deceasedBoolean:
              type: string
              description:
                true or false.  Implicitly true with deceasedDateTime value
            deceasedDateTime:
              type: string
              description: valid FHIR datetime string defining time of death
    responses:
      200:
        description:
          Returns updated [FHIR patient
          resource](http://www.hl7.org/fhir/patient.html) in JSON.
      400:
        description:
          if given parameters don't function, such as a false deceasedBoolean AND
          a deceasedDateTime value.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
    if not request.json or set(request.json.keys()).isdisjoint(
            {'deceasedDateTime', 'deceasedBoolean'}):
        abort(400, "Requires deceasedDateTime or deceasedBoolean in JSON")

    patient.update_deceased(request.json)
    db.session.commit()
    auditable_event("updated demographics on user {0} from input {1}".format(
        patient.id, json.dumps(request.json)), user_id=current_user().id,
        subject_id=patient.id, context='user')

    return jsonify(patient.as_fhir(include_empties=False))


@patient_api.route('/api/patient/<int:patient_id>/birthdate', methods=('POST',))
@patient_api.route('/api/patient/<int:patient_id>/birthDate', methods=('POST',))
@oauth.require_oauth()
def post_patient_dob(patient_id):
    """POST date of birth for a patient

    This convenience API wraps the ability to set a patient's birthDate - generally
    the /api/demographics API should be preferred.

    ---
    tags:
      - Patient
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: dob_details
          properties:
            birthDate:
              type: string
              description: valid FHIR date string defining date of birth
    responses:
      200:
        description:
          Returns updated [FHIR patient
          resource](http://www.hl7.org/fhir/patient.html) in JSON.
      400:
        description:
          if given parameters don't validate
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to edit requested patient

    """
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
    if not request.json or 'birthDate' not in request.json:
        abort(400, "Requires `birthDate` in JSON")

    patient.update_birthdate(request.json)
    db.session.commit()
    auditable_event("updated demographics on user {0} from input {1}".format(
        patient.id, json.dumps(request.json)), user_id=current_user().id,
        subject_id=patient.id, context='user')

    return jsonify(patient.as_fhir(include_empties=False))
