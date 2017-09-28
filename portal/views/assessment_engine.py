"""Assessment Engine API view functions"""
from flask import abort, Blueprint, current_app, jsonify, request, redirect, Response
from flask import session
from flask_swagger import swagger
from flask_user import roles_required
import jsonschema
import requests
from sqlalchemy.orm.exc import NoResultFound

from ..audit import auditable_event
from ..database import db
from ..date_tools import FHIR_datetime
from ..extensions import oauth
from ..models.assessment_status import AssessmentStatus
from ..models.assessment_status import invalidate_assessment_status_cache
from ..models.assessment_status import overall_assessment_status
from ..models.auth import validate_origin
from ..models.fhir import QuestionnaireResponse, EC, aggregate_responses, generate_qnr_csv
from ..models.intervention import INTERVENTION
from ..models.questionnaire import Questionnaire
from ..models.questionnaire_bank import QuestionnaireBank
from ..models.role import ROLE
from ..models.user import current_user, get_user, User
from .portal import check_int

assessment_engine_api = Blueprint('assessment_engine_api', __name__,
                                  url_prefix='/api')


@assessment_engine_api.route(
    '/patient/<int:patient_id>/assessment',
    defaults={'instrument_id': None},
)
@assessment_engine_api.route(
    '/patient/<int:patient_id>/assessment/<string:instrument_id>'
)
@oauth.require_oauth()
def assessment(patient_id, instrument_id):
    """Return a patient's responses to a questionnaire

    Retrieve a minimal FHIR doc in JSON format including the
    'QuestionnaireResponse' resource type.
    ---
    operationId: getQuestionnaireResponse
    tags:
      - Assessment Engine
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH patient ID
        required: true
        type: integer
        format: int64
      - name: instrument_id
        in: path
        description:
          ID of the instrument, eg "epic26", "eq5d"
        required: true
        type: string
        enum:
          - epic26
          - eq5d

    responses:
      200:
        description: successful operation
        schema:
          id: assessment_bundle
          required:
            - type
          properties:
            type:
                description:
                  Indicates the purpose of this bundle- how it was
                  intended to be used.
                type: string
                enum:
                  - document
                  - message
                  - transaction
                  - transaction-response
                  - batch
                  - batch-response
                  - history
                  - searchset
                  - collection
            link:
              description:
                A series of links that provide context to this bundle.
              items:
                properties:
                  relation:
                    description:
                      A name which details the functional use for
                      this link - see [[http://www.iana.org/assignments/link-relations/link-relations.xhtml]].
                  url:
                    description: The reference details for the link.
            total:
                description:
                  If a set of search matches, this is the total number of
                  matches for the search (as opposed to the number of
                  results in this bundle).
                type: integer
            entry:
              type: array
              items:
                $ref: "#/definitions/QuestionnaireResponse"
          example:
            entry:
            - resourceType: QuestionnaireResponse
              authored: '2016-01-22T20:32:17Z'
              status: completed
              identifier:
                value: '101.0'
                use: official
                label: cPRO survey session ID
              subject:
                display: patient demographics
                reference: https://stg.us.truenth.org/api/demographics/10015
              author:
                display: patient demographics
                reference: https://stg.us.truenth.org/api/demographics/10015
              source:
                display: patient demographics
                reference: https://stg.us.truenth.org/api/demographics/10015
              group:
                question:
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.1.5
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 5
                  linkId: epic26.1
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.2.4
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 4
                  linkId: epic26.2
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.3.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.3
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.4.3
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.4
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.5.1
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 0
                  linkId: epic26.5
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.6.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.6
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.7.3
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.7
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.8.4
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 3
                  linkId: epic26.8
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.9.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.9
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.10.1
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 0
                  linkId: epic26.10
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.11.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.11
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.12.3
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.12
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.13.4
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 3
                  linkId: epic26.13
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.14.5
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 4
                  linkId: epic26.14
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.15.4
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 4
                  linkId: epic26.15
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.16.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.16
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.17.1
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.17
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.18.1
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.18
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.19.3
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 3
                  linkId: epic26.19
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.20.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.20
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.21.4
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 4
                  linkId: epic26.21
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.22.1
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 0
                  linkId: epic26.22
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.23.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.23
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.24.3
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.24
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.25.3
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.25
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.26.3
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.26
              questionnaire:
                display: EPIC 26 Short Form
                reference: https://stg.us.truenth.org/api/questionnaires/epic26
            - resourceType: QuestionnaireResponse
              authored: '2016-03-11T23:47:28Z'
              status: completed
              identifier:
                value: '119.0'
                use: official
                label: cPRO survey session ID
              subject:
                display: patient demographics
                reference: https://stg.us.truenth.org/api/demographics/10015
              author:
                display: patient demographics
                reference: https://stg.us.truenth.org/api/demographics/10015
              source:
                display: patient demographics
                reference: https://stg.us.truenth.org/api/demographics/10015
              group:
                question:
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.1.1
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.1
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.2.1
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.2
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.3.3
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.3
                - answer: []
                  linkId: epic26.4
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.5.4
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 3
                  linkId: epic26.5
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.6.3
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.6
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.7.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.7
                - answer: []
                  linkId: epic26.8
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.9.3
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 3
                  linkId: epic26.9
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.10.5
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 4
                  linkId: epic26.10
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.11.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.11
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.12.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.12
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.13.4
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 3
                  linkId: epic26.13
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.14.1
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 0
                  linkId: epic26.14
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.15.5
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 5
                  linkId: epic26.15
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.16.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.16
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.17.1
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.17
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.18.4
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 4
                  linkId: epic26.18
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.19.4
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 4
                  linkId: epic26.19
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.20.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.20
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.21.5
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 5
                  linkId: epic26.21
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.22.1
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 0
                  linkId: epic26.22
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.23.2
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 1
                  linkId: epic26.23
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.24.3
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 2
                  linkId: epic26.24
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.25.4
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 3
                  linkId: epic26.25
                - answer:
                  - valueCoding:
                      system: https://stg.us.truenth.org/api/codings/assessment
                      code: epic26.26.5
                      extension:
                        url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                        valueDecimal: 4
                  linkId: epic26.26
              questionnaire:
                display: EPIC 26 Short Form
                reference: https://stg.us.truenth.org/api/questionnaires/epic26
            link:
              href: https://stg.us.truenth.org/api/patient/10015/assessment/epic26
              rel: self
            resourceType: Bundle
            total: 2
            type: searchset
            updated: '2016-03-14T20:47:26.282263Z'
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """

    current_user().check_role(permission='view', other_id=patient_id)
    patient = get_user(patient_id)
    if patient.deleted:
        abort(400, "deleted user - operation not permitted")
    questionnaire_responses = QuestionnaireResponse.query.filter_by(subject_id=patient_id).order_by(QuestionnaireResponse.authored.desc())

    instrument_id = request.args.get('instrument_id', instrument_id)
    if instrument_id is not None:
        questionnaire_responses = questionnaire_responses.filter(
            QuestionnaireResponse.document[
                ("questionnaire", "reference")
            ].astext.endswith(instrument_id)
        )

    documents = [qnr.document for qnr in questionnaire_responses]

    bundle = {
        'resourceType':'Bundle',
        'updated':FHIR_datetime.now(),
        'total':len(documents),
        'type': 'searchset',
        'link': {
            'rel':'self',
            'href':request.url,
        },
        'entry':documents,
    }

    return jsonify(bundle)


@assessment_engine_api.route('/patient/assessment')
@roles_required([ROLE.STAFF_ADMIN, ROLE.STAFF, ROLE.RESEARCHER])
@oauth.require_oauth()
def get_assessments():
    """
    Return multiple patient's responses to all questionnaires

    NB list of patient's returned is limited by current_users implicit
    permissions, typically controlled through organization affiliation.

    ---
    operationId: getQuestionnaireResponses
    tags:
      - Assessment Engine
    parameters:
      - name: format
        in: query
        description: format of file to download (CSV or JSON)
        required: false
        type: string
        enum:
          - json
          - csv
        default: json
      - name: instrument_id
        in: query
        description:
          ID of the instrument, eg "epic26", "eq5d"
        required: false
        type: array
        items:
          type: string
          enum:
            - epic26
            - eq5d
        collectionFormat: multi
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: assessments_bundle
          required:
            - type
          properties:
            type:
                description:
                  Indicates the purpose of this bundle- how it was
                  intended to be used.
                type: string
                enum:
                  - document
                  - message
                  - transaction
                  - transaction-response
                  - batch
                  - batch-response
                  - history
                  - searchset
                  - collection
            link:
              description:
                A series of links that provide context to this bundle.
              items:
                properties:
                  relation:
                    description:
                      A name which details the functional use for
                      this link - see [[http://www.iana.org/assignments/link-relations/link-relations.xhtml]].
                  url:
                    description: The reference details for the link.
            total:
                description:
                  If a set of search matches, this is the total number of
                  matches for the search (as opposed to the number of
                  results in this bundle).
                type: integer
            entry:
              type: array
              items:
                $ref: "#/definitions/FHIRPatient"
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    # Rather than call current_user.check_role() for every patient
    # in the bundle, deligate that responsibility to aggregate_responses()
    bundle = aggregate_responses(
        instrument_ids=request.args.getlist('instrument_id'),
        current_user=current_user()
    )
    bundle.update({
        'link': {
            'rel':'self',
            'href':request.url,
        },
    })

    # Default to JSON output if format unspecified
    if request.args.get('format', 'json') == 'json':
        return jsonify(bundle)


    return Response(
        generate_qnr_csv(bundle),
        mimetype='text/csv',
        headers={
            "Content-Disposition":
                "attachment;filename=qnr_data-%s.csv" % FHIR_datetime.now()
        }
    )

@assessment_engine_api.route(
    '/patient/<int:patient_id>/assessment',
    methods=('PUT',),
)
@oauth.require_oauth()
def assessment_update(patient_id):
    """Update an existing questionnaire response on a patient's record

    Submit a minimal FHIR doc in JSON format including the 'QuestionnaireResponse'
    resource type.
    ---
    operationId: updateQuestionnaireResponse
    tags:
      - Assessment Engine
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
          $ref: "#/definitions/QuestionnaireResponse"
    responses:
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
      404:
        description: existing QuestionnaireResponse not found
    """

    if not hasattr(request, 'json') or not request.json:
        abort(400, 'Invalid request')

    # Verify the current user has permission to edit given patient
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user(patient_id)
    if patient.deleted:
        abort(400, "deleted user - operation not permitted")

    swag = swagger(current_app)

    draft4_schema = {
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'type': 'object',
        'definitions': swag['definitions'],
    }

    validation_schema = 'QuestionnaireResponse'
    # Copy desired schema (to validate against) to outermost dict
    draft4_schema.update(swag['definitions'][validation_schema])

    response = {
        'ok': False,
        'message': 'error updating questionnaire response',
        'valid': False,
    }

    updated_qnr = request.json

    try:
        jsonschema.validate(updated_qnr, draft4_schema)
    except jsonschema.ValidationError as e:
        return jsonify({
            'ok': False,
            'message': e.message,
            'reference': e.schema,
        })
    else:
        response.update({
            'ok': True,
            'message': 'questionnaire response valid',
            'valid': True,
        })

    # Todo: enforce identifier uniqueness at initial submission
    try:
        existing_qnr = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.document["identifier"] == updated_qnr["identifier"]
        ).one()
    # except NoResultException:
    except NoResultFound:
        abort(404,"existing QuestionnaireResponse not found")
    else:
        response.update({'message': 'previous questionnaire response found'})

    existing_qnr.status = updated_qnr["status"]
    existing_qnr.document = updated_qnr
    db.session.add(existing_qnr)
    db.session.commit()
    auditable_event(
        "updated {}".format(existing_qnr),
        user_id=current_user().id,
        subject_id=patient_id,
        context='assessment',
    )
    response.update({'message': 'questionnaire response updated successfully'})
    return jsonify(response)

@assessment_engine_api.route(
    '/patient/<int:patient_id>/assessment',
    methods=('POST',),
)
@oauth.require_oauth()
def assessment_add(patient_id):
    """Add a questionnaire response to a patient's record

    Submit a minimal FHIR doc in JSON format including the 'QuestionnaireResponse'
    resource type.
    ---
    operationId: addQuestionnaireResponse
    tags:
      - Assessment Engine
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
          id: QuestionnaireResponse
          description:
            A patient's responses to a questionnaire (a set of instruments,
            some standardized, some not), and metadata about the presentation
            and context of the assessment session (date, etc).
          required:
            - status
          properties:
            status:
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.status
              description:
                  The lifecycle status of the questionnaire response as a whole
              type: string
              enum:
                - in-progress
                - completed
            subject:
              schema:
                id: Reference
                type: object
                description: A reference from one resource to another
                properties:
                  reference:
                    type: string
                    externalDocs:
                      url: http://hl7.org/implement/standards/fhir/DSTU2/references-definitions.html#Reference.reference
                  display:
                    type: string
                    externalDocs:
                      url: http://hl7.org/implement/standards/fhir/DSTU2/references-definitions.html#Reference.display
            author:
              $ref: "#/definitions/Reference"
            authored:
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.authored
              description: The datetime this resource was last updated
              type: string
              format: date-time
            source:
              $ref: "#/definitions/Reference"
            group:
              schema:
                id: group
                description:
                  A group of related questions or sub-groups. May only
                  contain either questions or groups
                properties:
                  group:
                    $ref: "#/definitions/group"
                  title:
                    type: string
                    description: Group name
                    externalDocs:
                      url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.group.title
                  text:
                    type: string
                    description: Additional text for this group
                    externalDocs:
                      url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.group.text
                  question:
                    description:
                      Set of questions within this group. The order of
                      questions within the group is relevant.
                    type: array
                    externalDocs:
                      url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.group.question
                    items:
                      description: An individual question and related attributes
                      type: object
                      properties:
                        text:
                          type: string
                          description: Question text
                        answer:
                          type: array
                          description:
                            The respondent's answer(s) to the question
                          externalDocs:
                            url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.group.question.answer
                          items:
                            description:
                              An individual answer to a question and related
                              attributes. May only contain a single `value[x]`
                              attribute
                            type: object
                            externalDocs:
                              url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.group.question.answer.value_x_
                            properties:
                              valueBoolean:
                                type: boolean
                                description: Boolean value answer to a question
                              valueDecimal:
                                type: number
                                description: Decimal value answer to a question
                              valueInteger:
                                type: integer
                                description: Integer value answer to a question
                              valueDate:
                                type: string
                                format: date
                                description: Date value answer to a question
                              valueDateTime:
                                type: string
                                format: date-time
                                description: Datetime value answer to a question
                              valueInstant:
                                type: string
                                format: date-time
                                description: Instant value answer to a question
                              valueTime:
                                type: string
                                description: Time value answer to a question
                              valueString:
                                type: string
                                description: String value answer to a question
                              valueUri:
                                type: string
                                description: URI value answer to a question
                              valueAttachment:
                                type: object
                                description:
                                  Attachment value answer to a question
                              valueCoding:
                                type: object
                                description:
                                  Coding value answer to a question, may
                                  include score as FHIR extension
                                properties:
                                  system:
                                    description:
                                      Identity of the terminology system
                                    type: string
                                    format: uri
                                  version:
                                    description:
                                      Version of the system - if relevant
                                    type: string
                                  code:
                                    description:
                                      Symbol in syntax defined by the system
                                    type: string
                                  display:
                                    description:
                                      Representation defined by the system
                                    type: string
                                  userSelected:
                                    description:
                                      If this coding was chosen directly by
                                      the user
                                    type: boolean
                                  extension:
                                    description:
                                      Extension - Numerical value associated
                                      with the code
                                    type: object
                                    properties:
                                      url:
                                        description:
                                          Hardcoded reference to extension
                                        type: string
                                        format: uri
                                      valueDecimal:
                                        description: Numeric score value
                                        type: number
                              valueQuantity:
                                type: object
                                description:
                                  Quantity value answer to a question
                              valueReference:
                                type: object
                                description:
                                  Reference value answer to a question
                              group:
                                $ref: "#/definitions/group"
          example:
            resourceType: QuestionnaireResponse
            authored: '2016-03-11T23:47:28Z'
            status: completed
            identifier:
              value: '119.0'
              use: official
              label: cPRO survey session ID
            subject:
              display: patient demographics
              reference: https://stg.us.truenth.org/api/demographics/10015
            author:
              display: patient demographics
              reference: https://stg.us.truenth.org/api/demographics/10015
            source:
              display: patient demographics
              reference: https://stg.us.truenth.org/api/demographics/10015
            group:
              question:
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.1.1
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 1
                linkId: epic26.1
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.2.1
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 1
                linkId: epic26.2
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.3.3
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 2
                linkId: epic26.3
              - answer: []
                linkId: epic26.4
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.5.4
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 3
                linkId: epic26.5
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.6.3
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 2
                linkId: epic26.6
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.7.2
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 1
                linkId: epic26.7
              - answer: []
                linkId: epic26.8
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.9.3
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 3
                linkId: epic26.9
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.10.5
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 4
                linkId: epic26.10
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.11.2
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 1
                linkId: epic26.11
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.12.2
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 1
                linkId: epic26.12
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.13.4
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 3
                linkId: epic26.13
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.14.1
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 0
                linkId: epic26.14
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.15.5
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 5
                linkId: epic26.15
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.16.2
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 2
                linkId: epic26.16
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.17.1
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 1
                linkId: epic26.17
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.18.4
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 4
                linkId: epic26.18
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.19.4
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 4
                linkId: epic26.19
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.20.2
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 2
                linkId: epic26.20
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.21.5
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 5
                linkId: epic26.21
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.22.1
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 0
                linkId: epic26.22
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.23.2
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 1
                linkId: epic26.23
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.24.3
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 2
                linkId: epic26.24
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.25.4
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 3
                linkId: epic26.25
              - answer:
                - valueCoding:
                    system: https://stg.us.truenth.org/api/codings/assessment
                    code: epic26.26.5
                    extension:
                      url: https://hl7.org/fhir/StructureDefinition/iso21090-CO-value
                      valueDecimal: 4
                linkId: epic26.26
            questionnaire:
              display: EPIC 26 Short Form
              reference: https://stg.us.truenth.org/api/questionnaires/epic26
    responses:
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    """

    if not hasattr(request, 'json') or not request.json:
        return abort(400, 'Invalid request')

    # Verify the current user has permission to edit given patient
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user(patient_id)
    if patient.deleted:
        abort(400, "deleted user - operation not permitted")

    swag = swagger(current_app)

    draft4_schema = {
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'type': 'object',
        'definitions': swag['definitions'],
    }

    validation_schema = 'QuestionnaireResponse'
    # Copy desired schema (to validate against) to outermost dict
    draft4_schema.update(swag['definitions'][validation_schema])

    response = {
        'ok': False,
        'message': 'error saving questionnaire reponse',
        'valid': False,
    }

    try:
        jsonschema.validate(request.json, draft4_schema)

    except jsonschema.ValidationError as e:
        response = {
            'ok': False,
            'message': e.message,
            'reference': e.schema,
        }
        return jsonify(response)

    response.update({
        'ok': True,
        'message': 'questionnaire response valid',
        'valid': True,
    })

    encounter = current_user().current_encounter
    if 'entry_method' in session:
        encounter_type = getattr(EC, session['entry_method'].upper()).codings[0]
        encounter.type.append(encounter_type)

    qnr_qb = None
    if "questionnaire" in request.json:
        qn_ref = request.json.get("questionnaire").get("reference")
        qn_name = qn_ref.split("/")[-1] if qn_ref else None
        qn = Questionnaire.query.filter_by(name=qn_name).first()
        qbd = QuestionnaireBank.most_current_qb(patient)
        qb = qbd.questionnaire_bank
        if (qb and qn and (qn.id in [qbq.questionnaire.id
                           for qbq in qb.questionnaires])):
            qnr_qb = qb

    questionnaire_response = QuestionnaireResponse(
        subject_id=patient_id,
        status=request.json["status"],
        document=request.json,
        encounter=encounter,
        questionnaire_bank=qnr_qb,
        qb_iteration=qbd.iteration
    )

    db.session.add(questionnaire_response)
    db.session.commit()
    auditable_event("added {}".format(questionnaire_response),
                    user_id=current_user().id, subject_id=patient_id,
                    context='assessment')
    response.update({'message': 'questionnaire response saved successfully'})

    invalidate_assessment_status_cache(patient.id)
    return jsonify(response)


@assessment_engine_api.route('/invalidate/<int:user_id>')
@oauth.require_oauth()
def invalidate(user_id):
    user = get_user(user_id)
    if not user:
        abort(404)
    invalidate_assessment_status_cache(user_id)
    return jsonify(invalidated=user.as_fhir())


@assessment_engine_api.route('/present-assessment')
@roles_required([ROLE.STAFF_ADMIN, ROLE.STAFF, ROLE.PATIENT])
@oauth.require_oauth()
def present_assessment(instruments=None):
    """Request that TrueNTH present an assessment via the assessment engine

    Redirects to the first assessment engine instance that is capable of
    administering the requested assessment
    ---
    operationId: present_assessment
    tags:
      - Assessment Engine
    produces:
      - text/html
    parameters:
      - name: instrument_id
        in: query
        description:
          ID of the instrument, eg "epic26", "eq5d"
        required: true
        type: array
        items:
          type: string
          enum:
            - epic26
            - eq5d
        collectionFormat: multi
      - name: resume_instrument_id
        in: query
        description:
          ID of the instrument, eg "epic26", "eq5d"
        required: true
        type: array
        items:
          type: string
          enum:
            - epic26
            - eq5d
        collectionFormat: multi
      - name: next
        in: query
        description: Intervention URL to return to after assessment completion
        required: true
        type: string
        format: url
      - name: subject_id
        in: query
        description: User ID to Collect QuestionnaireResponses as
        required: false
        type: integer
    responses:
      303:
        description: successful operation
        headers:
          Location:
            description:
              URL registered with assessment engine used to provide given
              assessment
            type: string
            format: url
      401:
        description: if missing valid OAuth token or bad `next` parameter

    """
    # Todo: replace with proper models
    configured_instruments = current_app.config['INSTRUMENTS']

    queued_instruments = request.args.getlist('instrument_id')
    resume_instruments = request.args.getlist('resume_instrument_id')

    # Hack to allow deprecated API to piggyback
    # Remove when deprecated_present_assessment() is fully removed
    if instruments is not None:
        queued_instruments = instruments

    # Combine requested instruments into single list, maintaining order
    common_instruments = resume_instruments + queued_instruments
    common_instruments = sorted(
        set(common_instruments),
        key=lambda x: common_instruments.index(x)
    )

    if set(common_instruments) - set(configured_instruments):
        abort(
            404,
            "No matching assessment found: %s" % (
                ", ".join(set(common_instruments) - set(configured_instruments))
            )
        )

    assessment_params = {
        "project": ",".join(common_instruments),
        "resume_instrument_id": ",".join(resume_instruments),
        "subject_id": request.args.get('subject_id'),
    }
    # Clear empty querystring params
    assessment_params = {k:v for k,v in assessment_params.items() if v}

    assessment_url = "".join((
        INTERVENTION.ASSESSMENT_ENGINE.link_url,
        "/surveys/new_session?",
        requests.compat.urlencode(assessment_params),
    ))

    # Temporarily persist entry method until QNR POSTed
    entry_methods = {'paper'}
    if (
        'entry_method' in request.args and
        request.args.get('entry_method') in entry_methods
    ):
        session['entry_method'] = request.args.get('entry_method')
        current_app.logger.debug(
            'storing session[entry_method]: %s', request.args.get('entry_method')
        )

    if 'next' in request.args:
        next_url = request.args.get('next')

        # Validate next URL the same way CORS requests are
        validate_origin(next_url)

        current_app.logger.debug('storing session[assessment_return]: %s',
                                 next_url)
        session['assessment_return'] = next_url

    return redirect(assessment_url, code=303)

@assessment_engine_api.route('/present-assessment/<instrument_id>')
@oauth.require_oauth()
def deprecated_present_assessment(instrument_id):
    current_app.logger.warning(
        "use of depricated API %s from referer %s",
        request.url,
        request.headers.get('Referer'),
    )

    return present_assessment(instruments=[instrument_id,])

@assessment_engine_api.route('/complete-assessment')
@oauth.require_oauth()
def complete_assessment():
    """Return to the last intervention that requested an assessment be presented

    Redirects to the URL passed to TrueNTH when present-assessment was last
    called (if valid) or TrueNTH home
    ---
    operationId: complete_assessment
    tags:
      - Internal
    produces:
      - text/html
    responses:
      303:
        description: successful operation
        headers:
          Location:
            description:
              URL passed to TrueNTH when present-assessment was last
              called (if valid) or TrueNTH home
            type: string
            format: url
      401:
        description: if missing valid OAuth token

    """

    next_url = session.pop("assessment_return", "/")
    entry_method = session.pop("entry_method", None)
    if entry_method:
        current_app.logger.debug("assessment complete via %s", entry_method)

    current_app.logger.debug("assessment complete, redirect to: %s", next_url)
    return redirect(next_url, code=303)


@assessment_engine_api.route('/consent-assessment-status')
@oauth.require_oauth()
def batch_assessment_status():
    """Return a batch of consent and assessment states for list of users

    ---
    operationId: batch_assessment_status
    tags:
      - Internal
    parameters:
      - name: user_id
        in: query
        description:
          TrueNTH user ID for assessment status lookup.  Any number of IDs
          may be provided
        required: true
        type: array
        items:
          type: integer
          format: int64
        collectionFormat: multi
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: batch_assessment_response
          properties:
            status:
              type: array
              items:
                type: object
                required:
                  - user_id
                  - consents
                properties:
                  user_id:
                    type: integer
                    format: int64
                    description: TrueNTH ID for user
                  consents:
                    type: array
                    items:
                      type: object
                      required:
                        - consent
                        - assessment_status
                      properties:
                        consent:
                          type: string
                          description: Details of the consent
                        assessment_status:
                          type: string
                          description: User's assessment status
      401:
        description: if missing valid OAuth token

    """
    acting_user = current_user()
    user_ids = request.args.getlist('user_id')
    if not user_ids:
        abort(400, "Requires at least one user_id")
    results = []
    for uid in user_ids:
        check_int(uid)
    users = User.query.filter(User.id.in_(user_ids))
    for user in users:
        if not acting_user.check_role('view', user.id):
            continue
        details = []
        assessment_status, _ = overall_assessment_status(user.id)
        for consent in user.all_consents:
            details.append(
                {'consent': consent.as_json(),
                 'assessment_status': assessment_status})
        results.append({'user_id': user.id, 'consents': details})

    return jsonify(status=results)


@assessment_engine_api.route(
    '/patient/<int:patient_id>/assessment-status'
)
@oauth.require_oauth()
def patient_assessment_status(patient_id):
    """Return to the assessment status for a given patient

    ---
    operationId: patient_assessment_status
    tags:
      - Assessment Engine
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH patient ID
        required: true
        type: integer
        format: int64
    produces:
      - application/json
    responses:
      200:
        description: return current overall assessment status of given patient
      400:
        description: if patient id is invalid
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    patient = get_user(patient_id)
    if patient:
        current_user().check_role(permission='view', other_id=patient_id)
        assessment_status = AssessmentStatus(user=patient)
        assessment_overall_status = (
                assessment_status.overall_status if assessment_status else
                None)
        return jsonify(assessment_status=assessment_overall_status)
    else:
        abort(400, "invalid patient id")


@assessment_engine_api.route('/questionnaire_bank')
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

    """
    bundle = QuestionnaireBank.generate_bundle()
    return jsonify(bundle)


@assessment_engine_api.route('/questionnaire')
@oauth.require_oauth()
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

    """
    bundle = Questionnaire.generate_bundle()
    return jsonify(bundle)


@assessment_engine_api.route('/questionnaire/<string:name>')
@oauth.require_oauth()
def get_questionnaire(name):
    """Return the specified Questionnaire

    ---
    operationId: get_questionnaire
    tags:
      - Assessment Engine
    parameters:
      - name: name
        in: path
        description: Questionnaire name
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

    """
    try:
        name = str(name)
    except ValueError, e:
        abort(400, "invalid input '{}' - must be a valid string".format(name))
    q = Questionnaire.query.filter_by(name=name).first()
    return jsonify(questionnaire=q.as_fhir())
