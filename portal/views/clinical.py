"""Clinical API view functions"""
from flask import Blueprint, abort, jsonify, request

from ..audit import auditable_event
from ..database import db
from ..extensions import oauth
from ..models.audit import Audit
from ..models.clinical_constants import CC
from ..models.observation import Observation
from ..models.value_quantity import ValueQuantity
from ..models.user import current_user, get_user_or_abort
from .crossdomain import crossdomain

clinical_api = Blueprint('clinical_api', __name__, url_prefix='/api')


@clinical_api.route(
    '/patient/<int:patient_id>/clinical/biopsy',
    methods=('OPTIONS', 'GET'))
@crossdomain(origin='*')
@oauth.require_oauth()
def biopsy(patient_id):
    """Simplified API for getting clinical biopsy data w/o FHIR

    Returns 'true', 'false' or 'unknown' for the patient's clinical biopsy
    value in JSON, i.e. '{"value": true}'
    ---
    tags:
      - Clinical
    operationId: getBiopsy
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH patient ID
        required: true
        type: integer
        format: int64
    responses:
      200:
        description:
          Returns clinical biopsy information for requested portal user id
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    return clinical_api_shortcut_get(patient_id=patient_id,
                                     codeable_concept=CC.BIOPSY)


@clinical_api.route(
    '/patient/<int:patient_id>/clinical/pca_diag',
    methods=('OPTIONS', 'GET'))
@crossdomain(origin='*')
@oauth.require_oauth()
def pca_diag(patient_id):
    """Simplified API for getting clinical PCa diagnosis status w/o FHIR

    Returns 'true', 'false' or 'unknown' for the patient's clinical PCa
    diagnosis value in JSON, i.e. '{"value": true}'
    ---
    tags:
      - Clinical
    operationId: getPCaDiagnosis
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH patient ID
        required: true
        type: integer
        format: int64
    responses:
      200:
        description:
          Returns 'true', 'false' or 'unknown' for the patient's clinical PCa
          diagnosis value in JSON
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    return clinical_api_shortcut_get(patient_id=patient_id,
                                     codeable_concept=CC.PCaDIAG)


@clinical_api.route(
    '/patient/<int:patient_id>/clinical/pca_localized',
    methods=('OPTIONS', 'GET'))
@crossdomain(origin='*')
@oauth.require_oauth()
def pca_localized(patient_id):
    """Simplified API for getting clinical PCaLocalized status w/o FHIR

    Returns 'true', 'false' or 'unknown' for the patient's clinical
    PCaLocalized diagnosis value in JSON, i.e. '{"value": true}'
    ---
    tags:
      - Clinical
    operationId: getPCaLocalized
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH patient ID
        required: true
        type: integer
        format: int64
    responses:
      200:
        description:
          Returns 'true', 'false' or 'unknown' for the patient's clinical
          PCaLocalized diagnosis value in JSON
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    return clinical_api_shortcut_get(patient_id=patient_id,
                                     codeable_concept=CC.PCaLocalized)


@clinical_api.route('/patient/<int:patient_id>/clinical/biopsy',
                    methods=('OPTIONS', 'POST', 'PUT'))
@crossdomain(origin='*')
@oauth.require_oauth()
def biopsy_set(patient_id):
    """Simplified API for setting clinical biopsy data w/o FHIR

    Requires a simple JSON doc to set value for biopsy: '{"value": true}'

    Returns a json friendly message, i.e. '{"message": "ok"}'

    Raises 401 if logged-in user lacks permission to edit requested
    patient.

    ---
    operationId: setBiopsy
    tags:
      - Clinical
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
          id: Biopsy
          required:
            - value
          properties:
            value:
              type: boolean
              description: has the patient undergone a biopsy
            status:
              type: string
              description: optional status such as 'final' or 'unknown'
    responses:
      200:
        description: successful operation
        schema:
          id: response_ok
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    return clinical_api_shortcut_set(patient_id=patient_id,
                                     codeable_concept=CC.BIOPSY)


@clinical_api.route('/patient/<int:patient_id>/clinical/pca_diag',
                    methods=('OPTIONS', 'POST', 'PUT'))
@crossdomain(origin='*')
@oauth.require_oauth()
def pca_diag_set(patient_id):
    """Simplified API for setting clinical PCa diagnosis status w/o FHIR

    Requires a simple JSON doc to set PCa diagnosis: '{"value": true}'

    Raises 401 if logged-in user lacks permission to edit requested
    patient.

    ---
    operationId: setPCaDiagnosis
    tags:
      - Clinical
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
          id: PCaDiagnosis
          required:
            - value
          properties:
            value:
              type: boolean
              description: the patient's PCa diagnosis
            status:
              type: string
              description: optional status such as 'final' or 'unknown'
    responses:
      200:
        description: successful operation
        schema:
          id: response_ok
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    return clinical_api_shortcut_set(patient_id=patient_id,
                                     codeable_concept=CC.PCaDIAG)


@clinical_api.route('/patient/<int:patient_id>/clinical/pca_localized',
                    methods=('OPTIONS', 'POST', 'PUT'))
@crossdomain(origin='*')
@oauth.require_oauth()
def pca_localized_set(patient_id):
    """Simplified API for setting clinical PCa localized status w/o FHIR

    Requires simple JSON doc to set PCaLocalized diagnosis: '{"value": true}'

    Raises 401 if logged-in user lacks permission to edit requested
    patient.

    ---
    operationId: setPCaLocalized
    tags:
      - Clinical
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
          id: PCaLocalized
          required:
            - value
          properties:
            value:
              type: boolean
              description: the patient's PCaLocalized diagnosis
            status:
              type: string
              description: optional status such as 'final' or 'unknown'
    responses:
      200:
        description: successful operation
        schema:
          id: response_ok
          required:
            - message
          properties:
            message:
              type: string
              description: Result, typically "ok"
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    return clinical_api_shortcut_set(patient_id=patient_id,
                                     codeable_concept=CC.PCaLocalized)


@clinical_api.route(
    '/patient/<int:patient_id>/clinical',
    methods=('OPTIONS', 'GET'))
@crossdomain(origin='*')
@oauth.require_oauth()
def clinical(patient_id):
    """Access clinical data as a FHIR bundle of observations (in JSON)

    Returns a patient's clinical data (eg TNM, Gleason score) as a FHIR
    bundle of observations (http://www.hl7.org/fhir/observation.html)
    in JSON.

    NB - currently out of FHIR DSTU2 spec by default.  Include query string
    parameter ``patch_dstu2=True`` to properly nest each practitioner under
    a ``resource`` attribute.  Please consider using, as this will become
    default behavior in the future.

    ---
    tags:
      - Clinical
    operationId: getPatientObservations
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH patient ID
        required: true
        type: integer
        format: int64
      - name: patch_dstu2
        in: query
        description: whether or not to make bundles DTSU2 compliant
        required: false
        type: boolean
        default: false
    responses:
      200:
        description:
          Returns clinical information for requested portal user id as a
          FHIR bundle of observations
          (http://www.hl7.org/fhir/observation.html) in JSON.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    current_user().check_role(permission='view', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
    patch_dstu2 = request.args.get('patch_dstu2', False)
    return jsonify(patient.clinical_history(
        requestURL=request.url, patch_dstu2=patch_dstu2))


@clinical_api.route('/patient/<int:patient_id>/clinical',
                    methods=('OPTIONS', 'POST', 'PUT'))
@crossdomain(origin='*')
@oauth.require_oauth()
def clinical_set(patient_id):
    """Add clinical entry via FHIR Resource Observation

    Submit a minimal FHIR doc in JSON format including the 'Observation'
    resource type, and any fields to retain.  NB, only a subset
    are persisted in the portal including {"name"(CodeableConcept),
    "valueQuantity", "status", "issued", "performer"} - others will be ignored.

    Returns details of the change in the json 'message' field.

    If *performer* isn't defined, the current user is assumed.

    Raises 401 if logged-in user lacks permission to edit requested
    patient.

    ---
    operationId: addPatientObservation
    tags:
      - Clinical
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
          id: FHIRObservation
          required:
            - resourceType
          properties:
            resourceType:
              type: string
              description:
                defines FHIR resource type, must be Observation
                http://www.hl7.org/fhir/observation.html
    responses:
      200:
        description: successful operation
        schema:
          id: response_details
          required:
            - message
          properties:
            message:
              type: string
              description: details of the change
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
    if (not request.json or 'resourceType' not in request.json
            or request.json['resourceType'] != 'Observation'):
        abort(400, "Requires FHIR resourceType of 'Observation'")
    audit = Audit(
        user_id=current_user().id, subject_id=patient.id,
        context='observation')
    code, result = patient.add_observation(request.json, audit)
    if code != 200:
        abort(code, result)
    db.session.commit()
    auditable_event(
        result, user_id=current_user().id, subject_id=patient.id,
        context='observation')
    return jsonify(message=result)


@clinical_api.route('/patient/<int:patient_id>/clinical/<int:observation_id>',
                    methods=(['OPTIONS', 'PUT']))
@crossdomain(origin='*')
@oauth.require_oauth()
def clinical_update(patient_id, observation_id):
    """Updates a FHIR Resource Observation clinical entry

    Submit a minimal FHIR doc in JSON format. NB, only a subset
    are persisted in the portal including {"name"(CodeableConcept),
    "valueQuantity", "status", "issued", "performer"} - others will be ignored.

    Returns json of the updated version in the response.

    Any fields that are not specified in the json request, will not be changed.

    Raises 401 if logged-in user lacks permission to edit requested
    patient.

    ---
    operationId: setPatientObservation
    tags:
      - Clinical
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH patient ID
        required: true
        type: integer
        format: int64
      - name: observation_id
        in: path
        description: Clinical Observation ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: FHIRObservation
    responses:
      200:
        description: successful operation
        schema:
          id: response_details
          required:
            - message
          properties:
            message:
              type: string
              description: details of the change
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
    if not request.json:
        abort(400, "No update data provided")
    observation = Observation.query.filter_by(id=observation_id).first()
    if not observation_id or not observation:
        abort(400, "No Observation found for provided ID")
    result = observation.update_from_fhir(request.json)
    auditable_event(
        'updated observation {}'.format(observation_id),
        user_id=current_user().id, subject_id=patient.id,
        context='observation')
    return jsonify(result)


def clinical_api_shortcut_set(patient_id, codeable_concept):
    """Helper for common code used in clincal api shortcuts"""
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
    if not request.json or 'value' not in request.json:
        abort(400, "Expects 'value' in JSON")
    value = str(request.json['value']).lower()
    if value not in ('true', 'false'):
        abort(400, "Expecting boolean for 'value'")

    truthiness = ValueQuantity(value=value, units='boolean')
    audit = Audit(user_id=current_user().id,
                  subject_id=patient_id, context='observation')
    patient.save_observation(
        codeable_concept=codeable_concept, value_quantity=truthiness,
        audit=audit, status=request.json.get('status'), issued=None)

    db.session.commit()
    auditable_event("set {0} {1} on user {2}".format(
        codeable_concept, truthiness, patient_id), user_id=current_user().id,
        subject_id=patient_id, context='observation')
    return jsonify(message='ok')


def clinical_api_shortcut_get(patient_id, codeable_concept):
    """Helper for common code used in clincal api shortcuts"""
    current_user().check_role(permission='view', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
    return jsonify(value=patient.concept_value(codeable_concept))
