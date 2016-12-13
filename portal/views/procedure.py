from flask import abort, jsonify, Blueprint, request

from ..audit import auditable_event
from ..extensions import db, oauth
from ..models.audit import Audit
from ..models.user import current_user, get_user
from ..models.procedure import Procedure


procedure_api = Blueprint('procedure_api', __name__, url_prefix='/api')

@procedure_api.route('/patient/<int:patient_id>/procedure')
@oauth.require_oauth()
def procedure(patient_id):
    """Access procedure data as a FHIR bundle of procedures (in JSON)

    Returns a patient's procedures data as a FHIR
    bundle of procedures (http://www.hl7.org/fhir/procedure.html)
    in JSON.
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

    """
    patient = get_user(patient_id)
    current_user().check_role(permission='view', other_id=patient_id)
    if patient.deleted:
        abort(400, "deleted user - operation not permitted")
    return jsonify(patient.procedure_history(requestURL=request.url))


@procedure_api.route('/procedure', methods=('POST',))
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
          id: response
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

    """
    # patient_id must first be parsed from the JSON subject field
    # standard role check is below after parse

    if not request.json or 'resourceType' not in request.json or\
            request.json['resourceType'] != 'Procedure':
        abort(400, "Requires FHIR resourceType of 'Procedure'")

    audit = Audit(user_id=current_user().id)
    procedure = Procedure.from_fhir(request.json, audit)
    if procedure.start_time.year < 1900:
        abort(400, "Invalid datetime; pre 1900")

    # check the permission now that we know the subject
    patient_id = procedure.user_id
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user(patient_id)
    patient.procedures.append(procedure)
    db.session.commit()
    auditable_event("added {}".format(procedure), user_id=current_user().id)
    return jsonify(message='added procedure', procedure_id=str(procedure.id))


@procedure_api.route('/procedure/<int:procedure_id>', methods=('DELETE',))
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
          id: response
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

    """
    procedure = Procedure.query.get_or_404(procedure_id)

    # check the permission now that we know the subject
    patient_id = procedure.user_id
    current_user().check_role(permission='edit', other_id=patient_id)
    db.session.delete(procedure)
    db.session.commit()
    auditable_event("deleted {}".format(procedure), user_id=current_user().id)
    return jsonify(message='deleted procedure')
