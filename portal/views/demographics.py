"""Demographics API view functions"""
from flask import abort, Blueprint, jsonify
from flask import current_app, request
import json

from ..audit import auditable_event
from ..models.reference import MissingReference
from ..models.user import current_user, get_user
from ..extensions import oauth
from ..extensions import db

demographics_api = Blueprint('demographics_api', __name__, url_prefix='/api')


@demographics_api.route('/demographics', defaults={'patient_id': None})
@demographics_api.route('/demographics/<int:patient_id>')
@oauth.require_oauth()
def demographics(patient_id):
    """Get patient demographics

    Return defined patient demographics fields (eg first name, last name,
    DOB, email, cell phone), as a FHIR patient resource (in JSON)

    For fields with values outside the defined FHIR patient resource
    (http://www.hl7.org/fhir/patient.html), look in the 'extension'
    list.  This includes 'race' and 'ethnicity'.  See example usage
    (http://hl7.org/fhir/patient-example-us-extensions.json.html)

    ---
    tags:
      - Demographics
    operationId: getPatientDemographics
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description:
          Optional TrueNTH patient ID, defaults to the authenticated user.
        required: true
        type: integer
        format: int64
    responses:
      200:
        description:
          Returns demographics for requested portal user id as a FHIR
          patient resource (http://www.hl7.org/fhir/patient.html) in JSON.
          Defaults to logged-in user if `patient_id` is not provided.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    if patient_id:
        current_user().check_role(permission='view', other_id=patient_id)
        patient = get_user(patient_id)
    else:
        patient = current_user()
    return jsonify(patient.as_fhir())


@demographics_api.route('/demographics/<int:patient_id>', methods=('PUT',))
@oauth.require_oauth()
def demographics_set(patient_id):
    """Update demographics via FHIR Resource Patient

    Submit a minimal FHIR doc in JSON format including the 'Patient'
    resource type, and any fields to set.

    For fields outside the defined patient resource
    (http://www.hl7.org/fhir/patient.html), include in the 'extension'
    list.  This includes 'race' and 'ethnicity'.  See example usage
    (http://hl7.org/fhir/patient-example-us-extensions.json.html)

    To link a patient with a clinic, use the 'careProvider' entity.  The
    clinic must already be a registered organization.  See the
    [organization endpoints](/dist/#!/Organization).

    NB - as a side effect, if the username is still 'Anonymous', the given
    first and last names will be used to generate a unique username of the
    format "FirstName LastName N", where an integer N will only be included
    if another matching username exists.

    ---
    operationId: setPatientDemographics
    tags:
      - Demographics
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH patient ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: FHIRPatient
          required:
            - resourceType
          properties:
            resourceType:
              type: string
              description: defines FHIR resource type, must be Patient
    responses:
      200:
        description:
          Returns updated demographics for requested portal user id as FHIR
          patient resource (http://www.hl7.org/fhir/patient.html) in JSON.
          Defaults to logged-in user if `patient_id` is not provided.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user(patient_id)
    if not request.json or 'resourceType' not in request.json or\
            request.json['resourceType'] != 'Patient':
        abort(400, "Requires FHIR resourceType of 'Patient'")
    try:
        patient.update_from_fhir(request.json)
    except MissingReference, e:
        current_app.logger.debug("Demographics PUT failed: {}".format(e))
        abort(400, str(e))
    db.session.commit()
    auditable_event("updated demographics on user {0} from input {1}".format(
        patient_id, json.dumps(request.json)), user_id=current_user().id)
    return jsonify(patient.as_fhir())

