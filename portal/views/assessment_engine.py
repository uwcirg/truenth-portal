"""Assessment Engine API view functions"""
from datetime import datetime

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    request,
    session,
    url_for,
)
from flask_babel import gettext as _
from flask_swagger import swagger
from flask_user import roles_required
import jsonschema
import requests
from sqlalchemy.orm.exc import NoResultFound

from ..audit import auditable_event
from ..database import db
from ..date_tools import FHIR_datetime
from ..extensions import oauth
from ..models.client import validate_origin
from ..models.encounter import EC
from ..models.fhir import bundle_results
from ..models.intervention import INTERVENTION
from ..models.qb_status import QB_Status
from ..models.qb_timeline import invalidate_users_QBT
from ..models.questionnaire import Questionnaire
from ..models.questionnaire_response import (
    QuestionnaireResponse,
    aggregate_responses,
    generate_qnr_csv,
)
from ..models.role import ROLE
from ..models.user import User, current_user, get_user_or_abort
from ..trace import dump_trace, establish_trace
from ..type_tools import check_int
from .crossdomain import crossdomain

assessment_engine_api = Blueprint('assessment_engine_api', __name__)


@assessment_engine_api.route(
    '/api/patient/<int:patient_id>/assessment',
    defaults={'instrument_id': None},
)
@assessment_engine_api.route(
    '/api/patient/<int:patient_id>/assessment/<string:instrument_id>'
)
@crossdomain()
@oauth.require_oauth()
def assessment(patient_id, instrument_id):
    """Return a patient's responses to questionnaire(s)

    Retrieve a minimal FHIR doc in JSON format including the
    'QuestionnaireResponse' resource type. If 'instrument_id'
    is excluded, the patient's QuestionnaireResponses for all
    instruments are returned.
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
      - name: patch_dstu2
        in: query
        description: whether or not to make bundles DTSU2 compliant
        required: false
        type: boolean
        default: false
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
    security:
      - ServiceToken: []

    """

    current_user().check_role(permission='view', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
    questionnaire_responses = QuestionnaireResponse.query.filter_by(
        subject_id=patient.id).order_by(QuestionnaireResponse.authored.desc())

    instrument_id = request.args.get('instrument_id', instrument_id)
    if instrument_id is not None:
        questionnaire_responses = questionnaire_responses.filter(
            QuestionnaireResponse.document[
                ("questionnaire", "reference")
            ].astext.endswith(instrument_id)
        )

    documents = []
    for qnr in questionnaire_responses:
        for question in qnr.document['group']['question']:
            for answer in question['answer']:
                # Hack: Extensions should be a list, correct in-place if need be
                # todo: migrate towards FHIR spec in persisted data
                if (
                    'extension' in answer.get('valueCoding', {}) and
                    not isinstance(
                        answer['valueCoding']['extension'], (tuple, list))
                ):
                    answer['valueCoding']['extension'] = [
                        answer['valueCoding']['extension']]

        # Hack: add missing "resource" wrapper for DTSU2 compliance
        # Remove when all interventions compliant
        if request.args.get('patch_dstu2'):
            qnr.document = {
                'resource': qnr.document,
                'fullUrl': request.url,
            }

        documents.append(qnr.document)

    link = {'rel': 'self', 'href': request.url}
    return jsonify(bundle_results(elements=documents, links=[link]))


@assessment_engine_api.route('/api/patient/assessment')
@crossdomain()
@roles_required(
    [ROLE.STAFF_ADMIN.value, ROLE.STAFF.value, ROLE.RESEARCHER.value])
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
      - name: patch_dstu2
        in: query
        description: whether or not to make bundles DTSU2 compliant
        required: false
        type: boolean
        default: false
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
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """
    # Rather than call current_user.check_role() for every patient
    # in the bundle, delegate that responsibility to aggregate_responses()
    bundle = aggregate_responses(
        instrument_ids=request.args.getlist('instrument_id'),
        current_user=current_user(),
        patch_dstu2=request.args.get('patch_dstu2'),
    )
    bundle.update({
        'link': {
            'rel': 'self',
            'href': request.url,
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
    '/api/patient/<int:patient_id>/assessment',
    methods=('PUT',),
)
@crossdomain()
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
    security:
      - ServiceToken: []

    """

    if not hasattr(request, 'json') or not request.json:
        abort(400, 'Invalid request')

    # Verify the current user has permission to edit given patient
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
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
            QuestionnaireResponse.document["identifier"]
            == updated_qnr["identifier"]
        ).one()
    # except NoResultException:
    except NoResultFound:
        abort(404, "existing QuestionnaireResponse not found")
    else:
        response.update({'message': 'previous questionnaire response found'})

    existing_qnr.status = updated_qnr["status"]
    existing_qnr.document = updated_qnr
    db.session.add(existing_qnr)
    db.session.commit()
    auditable_event(
        "updated {}".format(existing_qnr),
        user_id=current_user().id,
        subject_id=patient.id,
        context='assessment',
    )
    response.update({'message': 'questionnaire response updated successfully'})
    return jsonify(response)


@assessment_engine_api.route(
    '/api/patient/<int:patient_id>/assessment', methods=('POST',))
@crossdomain()
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
      - name: entry_method
        in: query
        description: Entry method such as `paper` if known
        required: false
        type: string
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
    security:
      - ServiceToken: []

    """
    from ..models.qb_timeline import invalidate_users_QBT  # avoid cycle

    if not hasattr(request, 'json') or not request.json:
        return abort(400, 'Invalid request')

    if "questionnaire" not in request.json:
        abort(400, "Requires `questionnaire` element")

    # Verify the current user has permission to edit given patient
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
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
    if 'entry_method' in request.args:
        encounter_type = getattr(
            EC, request.args['entry_method'].upper()).codings[0]
        encounter.type.append(encounter_type)

    qnr_qb = None
    authored = FHIR_datetime.parse(request.json['authored'])
    qn_ref = request.json.get("questionnaire").get("reference")
    qn_name = qn_ref.split("/")[-1] if qn_ref else None
    qn = Questionnaire.find_by_name(name=qn_name)
    qbstatus = QB_Status(patient, as_of_date=authored)
    qbd = qbstatus.current_qbd()
    if (
        qbd and qn and (qn.id in [
        qbq.questionnaire.id for qbq in
        qbd.questionnaire_bank.questionnaires])
    ):
        qnr_qb = qbd.questionnaire_bank
        qb_iteration = qbd.iteration
    # if a valid qb wasn't found, try the indefinite option
    else:
        qbd = qbstatus.current_qbd('indefinite')
        if (
            qbd and qn and (qn.id in [
            qbq.questionnaire.id for qbq in
            qbd.questionnaire_bank.questionnaires])
        ):
            qnr_qb = qbd.questionnaire_bank
            qb_iteration = qbd.iteration

    if not qnr_qb:
        current_app.logger.warning(
            "Received questionnaire_response yet current QBs for patient {}"
            "don't contain reference to given instrument {}".format(
                patient_id, qn_name))
        qnr_qb = None
        qb_iteration = None

    questionnaire_response = QuestionnaireResponse(
        subject_id=patient_id,
        status=request.json["status"],
        document=request.json,
        encounter=encounter,
        questionnaire_bank=qnr_qb,
        qb_iteration=qb_iteration
    )

    db.session.add(questionnaire_response)
    db.session.commit()
    auditable_event("added {}".format(questionnaire_response),
                    user_id=current_user().id, subject_id=patient_id,
                    context='assessment')
    response.update({'message': 'questionnaire response saved successfully'})

    invalidate_users_QBT(patient.id)
    return jsonify(response)


@assessment_engine_api.route('/api/invalidate/<int:user_id>')
@oauth.require_oauth()
def invalidate(user_id):
    from ..models.qb_timeline import invalidate_users_QBT  # avoid cycle

    user = get_user_or_abort(user_id)
    invalidate_users_QBT(user_id)
    return jsonify(invalidated=user.as_fhir())


@assessment_engine_api.route('/api/present-needed')
@roles_required([ROLE.STAFF_ADMIN.value, ROLE.STAFF.value, ROLE.PATIENT.value])
@oauth.require_oauth()
def present_needed():
    """Look up needed and in process q's for user and then present_assessment

    Takes the same attributes as present_assessment.

    If `authored` date is different from utcnow(), any instruments found to be
    in an `in_progress` state will be treated as if they haven't been started.

    """
    from ..models.qb_status import QB_Status  # avoid cycle

    subject_id = request.args.get('subject_id') or current_user().id
    subject = get_user_or_abort(subject_id)
    if subject != current_user():
        current_user().check_role(permission='edit', other_id=subject_id)

    as_of_date = FHIR_datetime.parse(
        request.args.get('authored'), none_safe=True)
    if not as_of_date:
        as_of_date = datetime.utcnow()
    assessment_status = QB_Status(subject, as_of_date=as_of_date)
    if assessment_status.overall_status == 'Withdrawn':
        abort(400, 'Withdrawn; no pending work found')

    args = dict(request.args.items())
    args['instrument_id'] = (
        assessment_status.instruments_needing_full_assessment(
            classification='all'))

    # Instruments in progress need special handling.  Assemble
    # the list of external document ids for reliable resume
    # behavior at external assessment intervention.
    resume_ids = assessment_status.instruments_in_progress(
        classification='all')
    if resume_ids:
        args['resume_identifier'] = resume_ids

    if not args.get('instrument_id') and not args.get('resume_identifier'):
        flash(_('All available questionnaires have been completed'))
        current_app.logger.debug('no assessments needed, redirecting to /')
        return redirect('/')

    url = url_for('.present_assessment', **args)
    return redirect(url, code=302)


@assessment_engine_api.route('/api/present-assessment')
@crossdomain()
@roles_required([ROLE.STAFF_ADMIN.value, ROLE.STAFF.value, ROLE.PATIENT.value])
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
      - name: authored
        in: query
        description: Override QuestionnaireResponse.authored with given datetime
        required: false
        type: string
        format: date-time
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
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """

    queued_instruments = request.args.getlist('instrument_id')
    resume_instruments = request.args.getlist('resume_instrument_id')
    resume_identifiers = request.args.getlist('resume_identifier')

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

    configured_instruments = Questionnaire.questionnaire_codes()
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
        "resume_identifier": ",".join(resume_identifiers),
        "subject_id": request.args.get('subject_id'),
        "authored": request.args.get('authored'),
        "entry_method": request.args.get('entry_method'),
    }
    # Clear empty querystring params
    assessment_params = {k: v for k, v in assessment_params.items() if v}

    assessment_url = "".join((
        INTERVENTION.ASSESSMENT_ENGINE.link_url,
        "/surveys/new_session?",
        requests.compat.urlencode(assessment_params),
    ))

    if 'next' in request.args:
        next_url = request.args.get('next')

        # Validate next URL the same way CORS requests are
        validate_origin(next_url)

        current_app.logger.debug('storing session[assessment_return]: %s',
                                 next_url)
        session['assessment_return'] = next_url

    return redirect(assessment_url, code=303)


@assessment_engine_api.route('/api/present-assessment/<instrument_id>')
@oauth.require_oauth()
def deprecated_present_assessment(instrument_id):
    current_app.logger.warning(
        "use of depricated API %s from referer %s",
        request.url,
        request.headers.get('Referer'),
    )

    return present_assessment(instruments=[instrument_id])


@assessment_engine_api.route('/api/complete-assessment')
@crossdomain()
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
    security:
      - ServiceToken: []
      - OAuth2AuthzFlow: []

    """

    next_url = session.pop("assessment_return", "/")

    # Logout Assessment Engine after survey completion
    for token in INTERVENTION.ASSESSMENT_ENGINE.client.tokens:
        if token.user != current_user():
            continue

        current_app.logger.debug(
            "assessment complete, logging out user: %s", token.user.id)
        INTERVENTION.ASSESSMENT_ENGINE.client.notify({
            'event': 'logout',
            'user_id': token.user.id,
            'refresh_token': token.refresh_token,
            'info': 'complete-assessment',
        })
        db.session.delete(token)
    db.session.commit()

    current_app.logger.debug("assessment complete, redirect to: %s", next_url)
    return redirect(next_url, code=303)


@assessment_engine_api.route('/api/consent-assessment-status')
@crossdomain()
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
    security:
      - ServiceToken: []

    """
    from ..models.qb_timeline import qb_status_visit_name

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
        status, _ = qb_status_visit_name(user.id, datetime.utcnow())
        for consent in user.all_consents:
            details.append(
                {'consent': consent.as_json(),
                 'assessment_status': str(status)})
        results.append({'user_id': user.id, 'consents': details})

    return jsonify(status=results)


@assessment_engine_api.route(
    '/api/patient/<int:patient_id>/assessment-status')
@crossdomain()
@oauth.require_oauth()
def patient_assessment_status(patient_id):
    """Return current assessment status for a given patient

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
      - name: as_of_date
        in: query
        description: Optional UTC datetime for times other than ``utcnow``
        required: false
        type: string
        format: date-time
      - name: purge
        in: query
        description: Optional trigger to purge any cached data for given
          user before (re)calculating assessment status
        required: false
        type: string
    produces:
      - application/json
    responses:
      200:
        description: return current assessment status of given patient
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
      404:
        description: if patient id is invalid
    security:
      - ServiceToken: []

    """
    from ..models.qb_status import QB_Status

    patient = get_user_or_abort(patient_id)
    current_user().check_role(permission='view', other_id=patient_id)

    date = request.args.get('as_of_date')
    date = FHIR_datetime.parse(date) if date else datetime.utcnow()

    trace = request.args.get('trace', False)
    if trace:
        establish_trace(
            "BEGIN trace for assessment-status on {}".format(patient_id))

    purge = request.args.get('purge', False)
    if purge == 'True':
        invalidate_users_QBT(patient_id)
    assessment_status = QB_Status(user=patient, as_of_date=date)

    # indefinite assessments don't affect overall status, but need to
    # be available if unfinished
    outstanding_indefinite_work = len(
        assessment_status.instruments_needing_full_assessment(
            classification='indefinite') +
        assessment_status.instruments_in_progress(classification='indefinite')
    )
    qbd = assessment_status.current_qbd()
    qb_name = qbd.questionnaire_bank.name if qbd else None
    response = {
        'assessment_status': str(assessment_status.overall_status),
        'outstanding_indefinite_work': outstanding_indefinite_work,
        'questionnaires_ids': (
            assessment_status.instruments_needing_full_assessment(
                classification='all')),
        'resume_ids': assessment_status.instruments_in_progress(
            classification='all'),
        'completed_ids': assessment_status.instruments_completed(
            classification='all'),
        'qb_name': qb_name
    }

    if trace:
        response['trace'] = dump_trace()

    return jsonify(response)
