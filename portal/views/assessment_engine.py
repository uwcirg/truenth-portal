"""Assessment Engine API view functions"""
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    request,
    session,
    url_for,
)
from flask_babel import gettext as _
from flask_user import roles_required
from urllib.parse import quote
import jsonschema
import requests

from ..audit import auditable_event
from ..database import db
from ..date_tools import FHIR_datetime
from ..extensions import oauth
from ..models.client import validate_origin
from ..models.encounter import EC
from ..models.fhir import bundle_results
from ..models.identifier import Identifier
from ..models.intervention import INTERVENTION
from ..models.qb_timeline import invalidate_users_QBT
from ..models.questionnaire import Questionnaire
from ..models.questionnaire_response import (
    NoFutureDates,
    QuestionnaireResponse,
)
from ..models.research_study import (
    ResearchStudy,
    research_study_id_from_questionnaire,
)
from ..models.role import ROLE
from ..models.user import current_user, get_user
from ..timeout_lock import LockTimeout, guarded_task_launch
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
    patient = get_user(
        patient_id, 'view', allow_on_url_authenticated_encounters=True)
    questionnaire_responses = QuestionnaireResponse.query.filter_by(
        subject_id=patient.id).order_by(
        QuestionnaireResponse.document['authored'].desc())

    instrument_id = request.args.get('instrument_id', instrument_id)
    if instrument_id is not None:
        questionnaire_responses = questionnaire_responses.filter(
            QuestionnaireResponse.document[
                ("questionnaire", "reference")
            ].astext.endswith(instrument_id)
        )

    documents = []
    for qnr in questionnaire_responses:
        # NB, document_answered returns a (potentially) modified *copy* of
        # the document, so changes aren't persisted or found in db session
        # cached objects.  see TN-2417 for example side-effects
        document = qnr.document_answered
        for question in document['group']['question']:
            for answer in question['answer']:
                # Hack: Extensions should be a list, correct in-place if need be
                # todo: migrate towards FHIR spec in persisted data
                if (
                    'extension' in answer.get('valueCoding', {}) and
                    not isinstance(answer['valueCoding']['extension'], (tuple, list))
                ):
                    answer['valueCoding']['extension'] = [answer['valueCoding']['extension']]

        # Hack: add missing "resource" wrapper for DTSU2 compliance
        # Remove when all interventions compliant
        if request.args.get('patch_dstu2'):
            document = {
                'resource': document,
                'fullUrl': request.url,
            }

        # No place within the FHIR spec to associate 'visit name' nor a
        # 'status' as per business rules (i.e. 'in-progress' becomes
        # 'partially completed' once the associated QB expires).
        # Use FHIR `extension`s to pass these fields to clients.
        extensions = qnr.extensions()
        if extensions:
            if 'extension' not in qnr.document:
                document['extension'] = []
            document['extension'].extend(extensions)

        documents.append(document)

    link = {'rel': 'self', 'href': request.url}
    return jsonify(bundle_results(elements=documents, links=[link]))


@assessment_engine_api.route(
    '/api/patient/<int:patient_id>/questionnaire_response/<int:qnr_id>'
)
@crossdomain()
@oauth.require_oauth()
def get_qnr_by_id(patient_id, qnr_id):
    """Return the patient's requested questionaire_response

    Retrieve a minimal FHIR doc in JSON format including the
    'QuestionnaireResponse' resource type.
    ---
    operationId: getQuestionnaireResponseById
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
      - name: qnr_id
        in: path
        description:
          ID (primary key) of the requested Questionnaire Response
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
          $ref: "#/definitions/QuestionnaireResponse"
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    patient = get_user(
        patient_id, 'view', allow_on_url_authenticated_encounters=True)
    qnr = QuestionnaireResponse.query.get(qnr_id)
    if not qnr:
        abort(404)

    if qnr.subject_id != patient.id:
        abort(
            400,
            "Requested patient doesn't own requested questionnaire_response")

    # NB, document_answered returns a (potentially) modified *copy* of
    # the document, so changes aren't persisted or found in db session
    # cached objects.  see TN-2417 for example side-effects
    document = qnr.document_answered
    for question in document['group']['question']:
        for answer in question['answer']:
            # Hack: Extensions should be a list, correct in-place if need be
            # todo: migrate towards FHIR spec in persisted data
            if (
                'extension' in answer.get('valueCoding', {}) and
                not isinstance(answer['valueCoding']['extension'], (tuple, list))
            ):
                answer['valueCoding']['extension'] = [answer['valueCoding']['extension']]

    # Hack: add missing "resource" wrapper for DTSU2 compliance
    # Remove when all interventions compliant
    if request.args.get('patch_dstu2'):
        document = {
            'resource': document,
            'fullUrl': request.url,
        }

    # No place within the FHIR spec to associate 'visit name' nor a
    # 'status' as per business rules (i.e. 'in-progress' becomes
    # 'partially completed' once the associated QB expires).
    # Use FHIR `extension`s to pass these fields to clients.
    extensions = qnr.extensions()
    if extensions:
        assert('extension' not in qnr.document)  # catch future collisions
        document['extension'] = extensions

    return jsonify(document)


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
    from ..tasks import research_report_task

    research_studies = set()
    questionnaire_list = request.args.getlist('instrument_id')
    for q in questionnaire_list:
        research_studies.add(research_study_id_from_questionnaire(q))
    if len(research_studies) != 1:
        abort(
            400,
            f"Requested instruments ({questionnaire_list}) span multiple "
            "research studies")
    research_study_id = research_studies.pop()
    if research_study_id is None:
        research_study_id = 0

    # This frequently takes over a minute to produce.  Generate a serializable
    # form of all args for reliable hand off to a background task.
    kwargs = {
        'instrument_ids': questionnaire_list,
        'research_study_id': research_study_id,
        'acting_user_id': current_user().id,
        'patch_dstu2': request.args.get('patch_dstu2'),
        'request_url': request.url,
        'lock_key': "research_report_task_lock",
        'response_format': request.args.get('format', 'json').lower()
    }

    try:
        # Hand the task off to the job queue, and return 202 with URL for
        # checking the status of the task
        task = guarded_task_launch(research_report_task, **kwargs)
        return jsonify({}), 202, {'Location': url_for(
            'portal.task_status', task_id=task.id, _external=True)}
    except LockTimeout:
        msg = (
            "The system is busy exporting a report for another user. "
            "Please try again in a few minutes.")
        response = make_response(msg, 502)
        response.mimetype = "text/plain"
        return response


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
        return jsonify(message='Invalid request - requires JSON'), 400

    if request.json.get('resourceType') != 'QuestionnaireResponse':
        return jsonify(
            message='Requires resourceType of "QuestionnaireResponse"'), 400

    # Verify the current user has permission to edit given patient
    patient = get_user(
        patient_id, 'edit', allow_on_url_authenticated_encounters=True)

    response = {
        'ok': False,
        'message': 'error updating questionnaire response',
        'valid': False,
    }

    updated_qnr = request.json

    try:
        QuestionnaireResponse.validate_document(updated_qnr)
        QuestionnaireResponse.validate_authored(
            FHIR_datetime.parse(updated_qnr.get('authored')))
    except (jsonschema.ValidationError, NoFutureDates) as e:
        current_app.logger.warning("Failed QNR schema validation, %s", str(e))
        return jsonify({
            'ok': False,
            'message': str(e),
            'reference': getattr(e, 'schema', ''),
        }), 400
    else:
        response.update({
            'ok': True,
            'message': 'questionnaire response valid',
            'valid': True,
        })

    try:
        identifier = Identifier.from_fhir(updated_qnr.get('identifier'))
    except ValueError as e:
        response['message'] = str(e)
        return jsonify(response), 400
    existing_qnr = QuestionnaireResponse.by_identifier(identifier)
    if existing_qnr.count() == 0:
        current_app.logger.warning(
            "attempted update on QuestionnaireResponse with unknown "
            "identifier {}".format(identifier))
        response['message'] = "existing QuestionnaireResponse not found"
        return jsonify(response), 404
    if existing_qnr.count() > 1:
        msg = ("can't update; multiple QuestionnaireResponses found with "
               "identifier {}".format(identifier))
        current_app.logger.warning(msg)
        response['message'] = msg
        return jsonify(msg), 409

    response.update({'message': 'previous questionnaire response found'})
    existing_qnr = existing_qnr.first()

    # TN-3184, report any in-process QNRs attempting to change authored dates
    date_change_snippet = ""
    if FHIR_datetime.parse(existing_qnr.document["authored"]) != FHIR_datetime.parse(updated_qnr["authored"]):
        date_change_snippet = f" UNEXPECTED authored change; was previously {existing_qnr.document['authored']}"
        current_app.logger.warning(date_change_snippet)

    existing_qnr.status = updated_qnr["status"]
    existing_qnr.document = updated_qnr
    db.session.add(existing_qnr)
    db.session.commit()
    research_study_id = existing_qnr.assign_qb_relationship(
        acting_user_id=current_user().id)

    # TODO: only extract QuestionnaireResponses where the corresponding Questionnaire has the SDC extension
    qn_name = existing_qnr.document.get("questionnaire").get("reference", '').split('/')[-1]
    if qn_name == 'ironman_ss' and existing_qnr.status == 'completed':
        from ..tasks import extract_observations_task
        extract_observations_task.apply_async(
            kwargs={'questionnaire_response_id': existing_qnr.id}
        )
    auditable_event(
        f"updated {existing_qnr}{date_change_snippet}",
        user_id=current_user().id,
        subject_id=patient.id,
        context='assessment',
    )
    response.update({'message': 'questionnaire response updated successfully'})
    if research_study_id is not None:
        invalidate_users_QBT(patient.id, research_study_id=research_study_id)
    return jsonify(response)


@assessment_engine_api.route(
    '/api/patient/<int:patient_id>/assessment', methods=('POST',))
@crossdomain()
@oauth.require_oauth()
def assessment_add(patient_id):
    """Add a questionnaire response to a patient's record

    Submit a minimal FHIR doc in JSON format including the
    'QuestionnaireResponse' resource type.

    NB, updates are only possible on QuestionnaireResponses for which a
    well defined ``identifer`` is included.  If included, this value must
    be distinct over (``system``, ``value``).  A duplicate submission will
    result in a ``409: conflict`` response, and refusal to retain the
    submission.

    ---
    operationId: addQuestionnaireResponse
    tags:
      - Assessment Engine
    definitions:
      - schema:
          id: Question
          description: An individual question and related attributes
          type: object
          externalDocs:
            url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.group.question
          additionalProperties: false
          properties:
            text:
              description: Question text
              type: string
            linkId:
              description: Corresponding question within Questionnaire
              type: string
            answer:
              description:
                The respondent's answer(s) to the question
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.group.question.answer
              type: array
              items:
                $ref: "#/definitions/Answer"
      - schema:
          id: Answer
          description:
            An individual answer to a question and related attributes.
            May only contain a single value[x] attribute
          type: object
          externalDocs:
            url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.group.question.answer.value_x_
          additionalProperties: false
          properties:
            valueBoolean:
              description: Boolean value answer to a question
              type: boolean
            valueDecimal:
              description: Decimal value answer to a question
              type: number
            valueInteger:
              description: Integer value answer to a question
              type: integer
            valueDate:
              description: Date value answer to a question
              type: string
              format: date
            valueDateTime:
              description: Datetime value answer to a question
              type: string
              format: date-time
            valueInstant:
              description: Instant value answer to a question
              type: string
              format: date-time
            valueTime:
              description: Time value answer to a question
              type: string
            valueString:
              description: String value answer to a question
              type: string
            valueUri:
              description: URI value answer to a question
              type: string
            valueAttachment:
              description: Attachment value answer to a question
              $ref: "#/definitions/ValueAttachment"
            valueCoding:
              description:
                Coding value answer to a question, may include score as
                FHIR extension
              $ref: "#/definitions/ValueCoding"
            valueQuantity:
              description: Quantity value answer to a question
              $ref: "#/definitions/Quantity"
            valueReference:
              description: Reference value answer to a question
              $ref: "#/definitions/Reference"
            group:
              description: Nested questionnaire group
              $ref: "#/definitions/Group"
      - schema:
          id: Group
          description:
            A structured set of questions and their answers. The
            questions are ordered and grouped into coherent subsets,
            corresponding to the structure of the grouping of the
            questionnaire being responded to.
          type: object
          additionalProperties: false
          properties:
            linkId:
              description:
                The item from the Questionnaire that corresponds to this item
                in the QuestionnaireResponse resource.
              type: string
            title:
              description: Name for this group
              type: string
            text:
              description:
                Text that is displayed above the contents of the group or as
                the text of the question being answered.
              type: string
            question:
              description: Questions in this group.
              items:
                $ref: "#/definitions/Question"
              type: array
            group:
              description:
                Questions or sub-groups nested beneath a question or group.
              items:
                $ref: "#/definitions/Group"
              type: array
      - schema:
          id: Quantity
          description:
            A measured amount (or an amount that can potentially be measured).
            Note that measured amounts include amounts that are not precisely
            quantified, including amounts involving arbitrary units and
            floating currencies.
          type: object
          additionalProperties: false
          properties:
            id:
              description:
                Unique id for the element within a resource (for internal
                references). This may be any string value that does not
                contain spaces.
              type: string
            value:
              description:
                The value of the measured amount. The value includes an
                implicit precision in the presentation of the value.
              type: number
            comparator:
              description:
                How the value should be understood and represented - whether
                the actual value is greater or less than the stated value due
                to measurement issues; e.g. if the comparator is \"\u003c\" ,
                then the real value is \u003c stated value.
              type: string
              enum:
                - "\u003c"
                - "\u003c\u003d"
                - "\u003e\u003d"
                - "\u003e"
            unit:
              description: A human-readable form of the unit.
              type: string
            system:
              description:
                The identification of the system that provides the coded form
                of the unit.
              type: string
            code:
              description:
                A computer processable form of the unit in some unit
                representation system.
              type: string
      - schema:
          id: Questionnaire
          type: object
          additionalProperties: false
          properties:
            display:
              description: Name of Questionnaire
              type: string
            reference:
              description: URI uniquely defining the Questionnaire
              type: string
      - schema:
          id: QuestionnaireResponse
          type: object
          required:
            - resourceType
            - status
          additionalProperties: false
          properties:
            identifier:
              description:
                A business identifier assigned to a particular completed
                (or partially completed) questionnaire.
              $ref: "#/definitions/Identifier"
            questionnaire:
              description:
                The Questionnaire that defines and organizes the questions
                for which answers are being provided.
              $ref: "#/definitions/Questionnaire"
            resourceType:
              description:
                defines FHIR resource type, must be QuestionnaireResponse
              type: string
            status:
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.status
              description:
                The lifecycle status of the questionnaire response as a
                whole.  If submitting a QuestionnaireResponse with status
                "in-progress", the ``identifier`` must also be well
                defined.  Without it, there's no way to reference it
                for updates.
              type: string
              enum:
                - in-progress
                - completed
            subject:
              description:
                The subject of the questionnaire response.  This could be
                a patient, organization, practitioner, device, etc.  This
                is who/what the answers apply to, but is not necessarily
                the source of information.
              $ref: "#/definitions/Reference"
            author:
              description:
                Person who received the answers to the questions in the
                QuestionnaireResponse and recorded them in the system.
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
              description:
                A group or question item from the original questionnaire for
                which answers are provided.
              type: object
              $ref: "#/definitions/Group"
            extension:
              description:
                FHIR Extensions
              type: array
              items:
                $ref: "#/definitions/ValueDateTimeExtension"

          example:
            resourceType: QuestionnaireResponse
            authored: '2016-03-11T23:47:28Z'
            status: completed
            identifier:
              value: '119.0'
              use: official
              label: cPRO survey session ID
              system: 'https://ae.us.truenth.org/eproms'
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
      - schema:
          id: Reference
          description: link to an internal or external resource
          type: object
          additionalProperties: false
          properties:
            reference:
              description: Relative, internal or absolute URL reference
              type: string
            display:
              description: Text alternative for the resource
              type: string
      - schema:
          id: ValueAttachment
          description: For referring to data content defined in other formats
          type: object
          additionalProperties: false
          properties:
            contentType:
              description:
                Identifies the type of the data in the attachment and allows
                a method to be chosen to interpret or render the data.
                Includes mime type parameters such as charset where
                appropriate.
              type: string
            language:
              description:
                The human language of the content. The value can be any valid
                value according to BCP 47.
              type: string
            data:
              description:
                The actual data of the attachment - a sequence of bytes,
                base64 encoded.
              type: string
              format: byte
            url:
              description: A location where the data can be accessed.
              type: string
            size:
              description:
                The number of bytes of data that make up this attachment
                (before base64 encoding, if that is done).
              type: integer
            hash:
              description:
                The calculated hash of the data using SHA-1.
                Represented using base64.
              type: string
              format: byte
            title:
              description:
                A label or set of text to display in place of the data.
              type: string
            creation:
              description: The date that the attachment was first created.
              type: string
              format: date-time
      - schema:
          id: ValueCoding
          type: object
          additionalProperties: false
          properties:
            system:
              description: Identity of the terminology system
              type: string
              format: uri
            version:
              description: Version of the system - if relevant
              type: string
            code:
              description: Symbol in syntax defined by the system
              type: string
            display:
              description: Representation defined by the system
              type: string
            userSelected:
              description: If this coding was chosen directly by the user
              type: boolean
            extension:
              description:
                Extension - Numerical value associated with the code
              $ref: "#/definitions/ValueDecimalExtension"
      - schema:
          id: ValueDecimalExtension
          type: object
          additionalProperties: false
          properties:
            url:
              description: Hardcoded reference to extension
              type: string
              format: uri
            valueDecimal:
              description: Numeric score value
              type: number
      - schema:
          id: ValueDateTimeExtension
          type: object
          additionalProperties: false
          properties:
            url:
              description: Reference to extension
              type: string
              format: uri
            valueDateTime:
              description: actual date of completion
              type: string
              format: date-time
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
          $ref: "#/definitions/QuestionnaireResponse"
    responses:
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    if not hasattr(request, 'json') or not request.json:
        return jsonify(message='Invalid request - requires JSON'), 400

    if request.json.get('resourceType') != 'QuestionnaireResponse':
        return jsonify(
            message='Requires resourceType of "QuestionnaireResponse"'), 400

    # Verify the current user has permission to edit given patient
    patient = get_user(
        patient_id, 'edit', allow_on_url_authenticated_encounters=True)

    response = {
        'ok': False,
        'message': 'error saving questionnaire response',
        'valid': False,
    }

    try:
        QuestionnaireResponse.validate_document(request.json)
        QuestionnaireResponse.validate_authored(
            FHIR_datetime.parse(request.json.get('authored')))
    except (jsonschema.ValidationError, NoFutureDates) as e:
        current_app.logger.warning("Failed QNR schema validation, %s", str(e))
        response = {
            'ok': False,
            'message': str(e),
            'reference': getattr(e, 'schema', ''),
        }
        return jsonify(response), 400

    identifier = None
    if 'identifier' in request.json:
        # Confirm it's unique, or raise 409
        try:
            identifier = Identifier.from_fhir(request.json['identifier'])
        except ValueError as e:
            response['message'] = str(e)
            return jsonify(response), 400

        existing_qnr = QuestionnaireResponse.by_identifier(identifier)
        if existing_qnr.count():
            msg = ("QuestionnaireResponse with matching {} already exists; "
                   "must be unique over (system, value)".format(identifier))
            current_app.logger.warning(msg)
            response['message'] = msg
            return jsonify(response), 409

    if request.json.get('status') == 'in-progress' and not identifier:
        msg = "Status {} received without the required identifier".format(
            request.json.get('status'))
        current_app.logger.warning(msg)
        response['message'] = msg
        return jsonify(response), 400

    response.update({
        'ok': True,
        'message': 'questionnaire response valid',
        'valid': True,
    })

    encounter = current_user().current_encounter()
    if QuestionnaireResponse.query.filter(
            QuestionnaireResponse.encounter_id == encounter.id).count():
        # Another QuestionnaireResponse already attached to this encounter,
        # force a refresh to maintain a discrete QNR <=> Encounter pair.
        encounter = current_user().current_encounter(force_refresh=True)

    if 'entry_method' in request.args:
        encounter_type = getattr(
            EC, request.args['entry_method'].upper()).codings[0]
        encounter.type.append(encounter_type)

    questionnaire_response = QuestionnaireResponse(
        subject_id=patient_id,
        status=request.json["status"],
        document=request.json,
        encounter=encounter,
    )

    db.session.add(questionnaire_response)
    db.session.commit()
    research_study_id = questionnaire_response.assign_qb_relationship(
        acting_user_id=current_user().id)


    # TODO: only extract QuestionnaireResponses where the corresponding Questionnaire has the SDC extension
    qn_name = questionnaire_response.document.get("questionnaire").get("reference", '').split('/')[-1]
    if qn_name == 'ironman_ss' and questionnaire_response.status == 'completed':
        from ..tasks import extract_observations_task
        extract_observations_task.apply_async(
            kwargs={'questionnaire_response_id': questionnaire_response.id}
        )

    auditable_event("added {}".format(questionnaire_response),
                    user_id=current_user().id, subject_id=patient_id,
                    context='assessment')
    response.update({'message': 'questionnaire response saved successfully'})

    if research_study_id is not None:
        invalidate_users_QBT(patient.id, research_study_id=research_study_id)
    return jsonify(response)


@assessment_engine_api.route('/api/invalidate/<int:user_id>')
@oauth.require_oauth()
def invalidate(user_id):
    user = get_user(user_id, 'edit')
    invalidate_users_QBT(user_id, research_study_id='all')
    return jsonify(invalidated=user.as_fhir())


@assessment_engine_api.route('/api/present-needed')
@roles_required([ROLE.STAFF_ADMIN.value, ROLE.STAFF.value, ROLE.PATIENT.value])
@oauth.require_oauth()
def present_needed():
    """Look up needed and in process q's for user and then present_assessment

    Takes the same attributes as present_assessment.

    If `authored` date is different from utcnow(), any instruments found to be
    in an `in_progress` state will be treated as if they haven't been started.

    Manages a single research study at a time.  For all research studies a
    user is enrolled in, present-needed on the first found with outstanding
    work.  Call again after completion to pick up the next study.

    """
    from ..models.qb_status import QB_Status  # avoid cycle

    subject_id = request.args.get('subject_id') or current_user().id
    subject = get_user(
        subject_id, 'edit', allow_on_url_authenticated_encounters=True)
    as_of_date = FHIR_datetime.parse(
        request.args.get('authored'), none_safe=True)
    if not as_of_date:
        as_of_date = datetime.utcnow()

    for rs in ResearchStudy.assigned_to(subject):
        assessment_status = QB_Status(
            subject, research_study_id=rs, as_of_date=as_of_date)
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

        if args.get('instrument_id') or args.get('resume_identifier'):
            # work to be done in this study, break out of loop
            break

    if not args.get('instrument_id') and not args.get('resume_identifier'):
        flash(_('All available questionnaires have been completed'))
        current_app.logger.debug('no assessments needed, redirecting to /')
        return redirect('/')

    url = url_for('.present_assessment', **args)

    if current_user().current_encounter().auth_method == "url_authenticated":
        current_app.logger.debug('redirect to confirm identity')
        return redirect('/confirm-identity?redirect_url={}'.format(quote(url)))

    current_app.logger.debug('present assessment url, redirecting to: %s', url)
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
        description: Override QuestionnaireResponse.authored with given
          datetime. Optionally set to value within desired visit if `actual`
          date is outside
        required: false
        type: string
        format: date-time
      - name: actual
        in: query
        description: actual date of completion, to be used exclusively
         outside of visit [start-expires) dates.  In such an event, `authored`
         should be set to valid datetime within desired visit
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
        "actual": request.args.get('actual'),
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
