"""Demographics API view functions"""
import json

from flask import Blueprint, abort, current_app, jsonify, request

from ..audit import auditable_event
from ..database import db
from ..extensions import oauth
from ..models.reference import MissingReference
from ..models.user import current_user, get_user
from .crossdomain import crossdomain

demographics_api = Blueprint('demographics_api', __name__, url_prefix='/api')


@demographics_api.route('/demographics', defaults={'patient_id': None})
@demographics_api.route('/demographics/<int:patient_id>')
@crossdomain()
@oauth.require_oauth()
def demographics(patient_id):
    """Get patient (or any user's) demographics

    Return defined patient demographics fields (eg first name, last name,
    DOB, email, cell phone), as a FHIR patient resource (in JSON)

    For fields with values outside the defined FHIR patient resource
    (http://www.hl7.org/fhir/patient.html), look in the 'extension'
    list.  This includes 'race' and 'ethnicity'.  See example usage
    (http://hl7.org/fhir/patient-example-us-extensions.json.html)

    A deceased patient will include ONE of 'deceasedBoolean' or
    'deceasedDateTime' - preferring deceasedDateTime if it is known.

    At some point this may be extended to return a more role specific FHIR
    resource.  At this time, all users, regardless of role, work with the
    FHIR patient resource type.  This API has no effect on the user's roles.
    Use the /api/roles endpoints for that purpose.

    NB - all `empty` values are stripped from the return data.  For example,
    if a user doesn't have a `first_name`, the ['name']['given'] field will
    not be present in the return structure.

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
    security:
      - ServiceToken: []

    """
    if patient_id is None:
        patient_id = current_user().id
    patient = get_user(
        patient_id, 'view', allow_on_url_authenticated_encounters=True)
    return jsonify(patient.as_fhir(include_empties=False))


@demographics_api.route('/demographics/<int:patient_id>', methods=('PUT',))
@crossdomain()
@oauth.require_oauth()
def demographics_set(patient_id):
    """Update demographics (for any user) via FHIR Resource Patient

    Submit a minimal FHIR doc in JSON format including the 'Patient'
    resource type, and any fields to set.

    If a field is provided, it must define the entire set of the respective
    field.  For example, if **careProvider** is included, and only mentions one
    of two clinics previously associated with the user, only the one provided
    will be retained.  Consider calling GET first.

    For fields outside the defined patient resource
    (http://www.hl7.org/fhir/DSTU2/patient.html), include in the 'extension'
    list.  This includes 'race' and 'ethnicity'.  See example usage
    (http://hl7.org/fhir/patient-example-us-extensions.json.html)

    To link a patient with a clinic, use the 'careProvider' entity.  The
    clinic must already be a registered organization.  See the
    [organization endpoints](/dist/#!/Organization).

    For deceased patients, include ONE of 'deceasedBoolean' or
    'deceasedDateTime' - preferring deceasedDateTime if it is known.

    At some point this may be extended to consume a more role specific FHIR
    resource.  At this time, all users, regardless of role, work with the
    FHIR patient resource type.  This API has no effect on the user's role.
    Use the /api/roles endpoints for that purpose.

    NB - although the email address may be viewed as an identifier, to alter
    its value, make use the appropriate telecom field.

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
    security:
      - ServiceToken: []

    """
    from ..models.patient_list import patient_list_update_patient
    patient = get_user(patient_id, 'edit')
    if not request.json:
        abort(
            400,
            "Requires JSON with submission including "
            "HEADER 'Content-Type: application/json'"
        )
    if request.json.get('resourceType') != 'Patient':
        abort(400, "Requires FHIR resourceType of 'Patient'")
    if request.json.get('organizations'):
        abort(
            400, "FHIR Patient Resource uses 'careProvider' for organizations")
    try:
        # As we allow partial updates, first create a full representation
        # of this user, and update with any provided elements
        complete = patient.as_fhir(include_empties=True)
        complete.update(request.json)
        patient.update_from_fhir(complete, acting_user=current_user())
    except MissingReference as e:
        current_app.logger.debug("Demographics PUT failed: {}".format(e))
        abort(400, str(e))
    except ValueError as e:
        current_app.logger.debug("Demographics PUT failed: {}".format(e))
        abort(400, str(e))
    db.session.commit()
    auditable_event("updated demographics on user {0} from input {1}".format(
        patient_id, json.dumps(request.json)), user_id=current_user().id,
        subject_id=patient_id, context='user')

    # update the patient_table cache with any change from above
    patient_list_update_patient(patient_id)

    return jsonify(patient.as_fhir(include_empties=False))
