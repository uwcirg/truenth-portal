from collections import defaultdict

from flask import Blueprint, abort, jsonify, request

from ..audit import auditable_event
from ..database import db
from ..extensions import oauth
from ..models.audit import Audit
from ..models.procedure import Procedure
from ..models.procedure_codes import TxNotStartedConstants, TxStartedConstants
from ..models.qb_timeline import invalidate_users_QBT
from ..models.user import current_user, get_user
from .crossdomain import crossdomain

procedure_api = Blueprint('procedure_api', __name__, url_prefix='/api')


@procedure_api.route('/patient/<int:patient_id>/procedure')
@crossdomain()
@oauth.require_oauth()
def procedure(patient_id):
    """Access procedure data as a FHIR bundle of procedures (in JSON)

    Returns a patient's procedures data as a FHIR
    bundle of procedures (http://www.hl7.org/fhir/procedure.html)
    in JSON.

    NB a procedure code may enumerate multiple coding values, from different
    coding systems.  Clients will typically react on (code, system) values of
    interest.

    ---
    tags:
      - Procedure
    operationId: getPatientProcedures
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
          Returns procedure information for requested portal user id as a
          FHIR bundle of procedures
          (http://www.hl7.org/fhir/procedure.html) in JSON.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    patient = get_user(
        patient_id, 'view', allow_on_url_authenticated_encounters=True)
    return jsonify(patient.procedure_history(requestURL=request.url))


@procedure_api.route('/procedure', methods=('POST',))
@crossdomain()
@oauth.require_oauth()
def post_procedure():
    """Add procedure via FHIR Procedure Resource

    Submit a minimal FHIR doc in JSON format of the 'Procedure'
    resource type.  NB, only a subset are persisted, all of which must
    be included in a submission:
        Patient reference in Procedure.subject
        Code in Procedure.code (pointing to a CodeableConcept) with
            *system* of http://snomed.info/sct
        Performed datetime, either a single moment as
            **performedDateTime** or a range in **performedPeriod**

    NB although the system will maintain CodeableConcepts with codings for
    all synonymous codes from different systems, only one code need be defined
    in the submission, say just the ICHOM system and code value.

    Valuesets available at `/api/procedure/valueset/{valueset}` list
    respective code values known to the system for procedures indicating
    patient treatment status.

    Raises 401 if logged-in user lacks permission to edit referenced
    patient.

    ---
    operationId: postProcedure
    tags:
      - Procedure
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          id: FHIRProcedure
          required:
            - resourceType
          properties:
            resourceType:
              type: string
              description:
                defines FHIR resource type, must be Procedure
                http://www.hl7.org/fhir/procedure.html
    responses:
      200:
        description: successful operation
        schema:
          id: response_success_POST
          required:
            - message
          properties:
            message:
              type: string
              description: success of the POST
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to edit referenced patient
    security:
      - ServiceToken: []

    """

    # patient_id must first be parsed from the JSON subject field
    # standard role check is below after parse

    if (
        any((
            not request.json,
            'resourceType' not in request.json,
            request.json['resourceType'] != 'Procedure'
        ))
    ):
        abort(400, "Requires FHIR resourceType of 'Procedure'")

    audit = Audit(
        user_id=current_user().id, subject_id=current_user().id,
        context='procedure')
    try:
        procedure = Procedure.from_fhir(request.json, audit)
        db.session.add(procedure)
        db.session.commit()
    except ValueError as e:
        abort(400, str(e))
    if procedure.start_time.year < 1900:
        abort(400, "Invalid datetime; pre 1900")

    # check the permission now that we know the subject
    patient_id = procedure.user_id
    patient = get_user(patient_id, 'edit')
    patient.procedures.append(procedure)
    db.session.commit()
    auditable_event(
        "added {}".format(procedure), user_id=current_user().id,
        subject_id=patient_id, context='procedure')
    invalidate_users_QBT(patient_id, research_study_id='all')
    return jsonify(message='added procedure', procedure_id=str(procedure.id))


@procedure_api.route('/procedure/<int:procedure_id>', methods=('DELETE',))
@crossdomain()
@oauth.require_oauth()
def procedure_delete(procedure_id):
    """Delete a procedure by ID.

    Raises 401 if logged-in user lacks permission to edit referenced
    patient (patient the procedure names as **subject**)..

    ---
    operationId: deleteProcedure
    tags:
      - Procedure
    produces:
      - application/json
    parameters:
      - name: procedure_id
        in: path
        description: TrueNTH procedure ID
        required: true
        type: integer
        format: int64
    responses:
      200:
        description: operation success
        schema:
          id: response_success_DELETE
          required:
            - message
          properties:
            message:
              type: string
              description: success of the DELETE
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to edit referenced patient
    security:
      - ServiceToken: []

    """
    procedure = Procedure.query.get_or_404(procedure_id)

    # check the permission now that we know the subject
    patient_id = procedure.user_id
    get_user(patient_id, permission='edit')
    db.session.delete(procedure)
    db.session.commit()
    auditable_event(
        "deleted {}".format(procedure), user_id=current_user().id,
        subject_id=patient_id, context='procedure')
    invalidate_users_QBT(patient_id, research_study_id='all')
    return jsonify(message='deleted procedure')


@procedure_api.route('/procedure/valueset/<valueset>')
@crossdomain()
def procedure_value_sets(valueset):
    """Returns Valueset for treatment {started,not-started} codes

    ---
    tags:
      - Procedure
      - Valueset
    operationId: procedure_value_sets
    produces:
      - application/json
    parameters:
      - name: valueset
        in: path
        description: Named valueset (either 'tx-started' or 'tx-not-started')
        required: true
        type: string
    responses:
      200:
        description:
          Returns FHIR like Valueset (https://www.hl7.org/FHIR/valueset.html)
          for requested coding type.
    security:
      - ServiceToken: []

    """
    options = ('tx-started', 'tx-not-started')
    if valueset not in options:
        abort(400, 'unknown valueset, supported options: {}'.format(options))

    if valueset == 'tx-started':
        condition = 'has'
        constants_class = TxStartedConstants
    else:
        condition = 'has not'
        constants_class = TxNotStartedConstants

    valueset = {
        "resourceType": "ValueSet",
        "title": valueset,
        "description": (
            "List of procedure codes known to indicate treatment {} "
            "stared.".format(condition)),
        "url": request.url,
        "compose": {"include": []}
    }

    code_by_system = defaultdict(list)
    for concept in constants_class():
        for code in concept.codings:
            code_by_system[code.system].append(code)

    for system in code_by_system.keys():
        item = {"system": system,
                "concept": [c.as_fhir() for c in code_by_system[system]]}
        valueset["compose"]["include"].append(item)

    return jsonify(**valueset)
