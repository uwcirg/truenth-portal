"""API view functions"""
from flask import abort, Blueprint, jsonify, make_response
from flask import current_app, render_template, request, url_for, redirect, session
from flask.ext.user import roles_required
from flask_swagger import swagger
import jsonschema


from ..audit import auditable_event

from ..models.auth import validate_client_origin
from ..models.fhir import CodeableConcept, ValueQuantity, Observation
from ..models.fhir import QuestionnaireResponse
from ..models.fhir import BIOPSY, PCaDIAG, TX
from ..models.role import ROLE, Role
from ..models.user import current_user, get_user
from ..extensions import oauth
from ..extensions import db
from .crossdomain import crossdomain

api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/me')
@oauth.require_oauth()
def me():
    """Access basics for current user

    returns logged in user's id, username and email in JSON
    ---
    tags:
      - User
    operationId: me
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: user
          required:
            - id
            - username
            - email
          properties:
            id:
              type: integer
              format: int64
              description: Central Services ID for user
            username:
              type: string
              description: User's username
            email:
              type: string
              description: User's preferred email address
      401:
        description: if missing valid OAuth token

    """
    user = current_user()
    return jsonify(id=user.id, username=user.username,
                   email=user.email)


@api.route('/demographics', defaults={'patient_id': None})
@api.route('/demographics/<int:patient_id>')
@oauth.require_oauth()
def demographics(patient_id):
    """Get patient demographics

    Return defined patient demographics fields (eg first name, last name,
    DOB, email, cell phone), as a FHIR patient resource (in JSON)
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


@api.route('/demographics/<int:patient_id>', methods=('POST', 'PUT'))
@oauth.require_oauth()
def demographics_set(patient_id):
    """Update demographics via FHIR Resource Patient

    Submit a minimal FHIR doc in JSON format including the 'Patient'
    resource type, and any fields to set.
    ---
    operationId: setPatientDemographics
    tags:
      - Demographics
    produces:
      - application/json
    parameters:
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
    patient.update_from_fhir(request.json)
    return jsonify(patient.as_fhir())


@api.route('/clinical/biopsy/<int:patient_id>')
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

    """
    return clinical_api_shortcut_get(patient_id=patient_id,
                                     codeable_concept=BIOPSY)


@api.route('/clinical/pca_diag/<int:patient_id>')
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

    """
    return clinical_api_shortcut_get(patient_id=patient_id,
                                     codeable_concept=PCaDIAG)



@api.route('/clinical/tx/<int:patient_id>')
@oauth.require_oauth()
def treatment(patient_id):
    """Simplified API for getting clinical treatment begun status w/o FHIR

    Returns 'true', 'false' or 'unknown' for the patient's clinical treatment
    begun value in JSON, i.e. '{"value": true}'
    ---
    tags:
      - Clinical
    operationId: getTx
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
          treatment begun status in JSON
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    return clinical_api_shortcut_get(patient_id=patient_id,
                                     codeable_concept=TX)



@api.route('/clinical/biopsy/<int:patient_id>', methods=('POST', 'PUT'))
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
              description: Result, typically "ok"
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    return clinical_api_shortcut_set(patient_id=patient_id,
                                     codeable_concept=BIOPSY)


@api.route('/clinical/pca_diag/<int:patient_id>', methods=('POST', 'PUT'))
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
              description: Result, typically "ok"
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    return clinical_api_shortcut_set(patient_id=patient_id,
                                     codeable_concept=PCaDIAG)


@api.route('/clinical/tx/<int:patient_id>', methods=('POST', 'PUT'))
@oauth.require_oauth()
def tx_set(patient_id):
    """Simplified API for setting clinical treatment status w/o FHIR

    Requires a simple JSON doc to set treatment status: '{"value": true}'

    Raises 401 if logged-in user lacks permission to edit requested
    patient.

    ---
    operationId: setTx
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
          id: Tx
          required:
            - value
          properties:
            value:
              type: boolean
              description: the patient's treatment status
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
              description: Result, typically "ok"
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    return clinical_api_shortcut_set(patient_id=patient_id, codeable_concept=TX)



@api.route('/clinical', defaults={'patient_id': None})
@api.route('/clinical/<int:patient_id>')
@oauth.require_oauth()
def clinical(patient_id):
    """Access clinical data as a FHIR bundle of observations (in JSON)

    Returns a patient's clinical data (eg TNM, Gleason score) as a FHIR
    bundle of observations (http://www.hl7.org/fhir/observation.html)
    in JSON.  Defaults to logged-in user if `patient_id` is not provided.
    ---
    tags:
      - Clinical
    operationId: getPatientObservations
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
          Returns clinical information for requested portal user id as a
          FHIR bundle of observations
          (http://www.hl7.org/fhir/observation.html) in JSON.
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
    return jsonify(patient.clinical_history(requestURL=request.url))


@api.route('/clinical/<int:patient_id>', methods=('POST', 'PUT'))
@oauth.require_oauth()
def clinical_set(patient_id):
    """Add clinical entry via FHIR Resource Observation

    Submit a minimal FHIR doc in JSON format including the 'Observation'
    resource type, and any fields to retain.  NB, only a subset
    are persisted in the portal including {"name"(CodeableConcept),
    "valueQuantity", "status", "issued"} - others will be ignored.

    Returns a json friendly message, i.e. {"message": "ok"}

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
        description:
          Optional TrueNTH patient ID, defaults to the authenticated user.
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
          id: response
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

    """
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user(patient_id)
    if not request.json or 'resourceType' not in request.json or\
            request.json['resourceType'] != 'Observation':
        abort(400, "Requires FHIR resourceType of 'Observation'")
    code, result = patient.add_observation(request.json)
    if code != 200:
        abort(code, result)
    return jsonify(message=result)


@api.route('/assessment', methods=('GET',))
@oauth.require_oauth()
def assessment(instrument_id):
    """Return a patient's responses to a questionnaire
    ---
    operationId: getQuestionnaireResponse
    tags:
      - QuestionnaireResponse
      - Assessment Engine 
    produces:
      - application/json
    parameters:
      - name: instrument_id
        in: query 
        description:
          ID of the instrument, eg "epic26", "eq5d" 
        required: true
        type: string
        enum:
          - epic26
          - eq5d 
      - name: patient_id
        in: query 
        description:
          Optional TrueNTH patient ID, defaults to the authenticated user.
        required: false
        type: integer
        format: int64

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
              description: Result, typically "ok"
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """

    # This is surely broken...
    questionnaire_response = QuestionnaireResponse.query.filter_by(id=instrument_id).first()
    #questionnaire_response = QuestionnaireResponse.query.filter_by(id=questionnaire_response_id).first()

    if not questionnaire_response:
        abort(404)

    return jsonify(questionnaire_response.document)

@api.route('/assessment/<int:patient_id>', methods=('POST', 'PUT'))
@api.route('/assessment/<int:patient_id>/', methods=('POST', 'PUT'))
@oauth.require_oauth()
def assessment_set(patient_id):
    """Add a questionnaire response to a patient's record

    Submit a minimal FHIR doc in JSON format including the 'QuestionnaireResponse'
    resource type.
    ---
    operationId: addQuestionnaireResponse
    tags:
      - QuestionnaireResponse
      - Assessment Engine 
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          id: QuestionnaireResponse
          description: A patient's responses to a questionnaire (a set of instruments, some standardized, some not), and metadata about the presentation and context of the assessment session (date, etc).
          externalDocs:
            url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse.html
          required:
            - status
          properties:
            status:
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.status
              description: The lifecycle status of the questionnaire response as a whole
              type: string
              enum:
                - in-progress
                - completed
            subject:
              description: The subject of the questionnaire response
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.subject
              schema:
                id: Reference
                type: object
                description: A reference from one resource to another
                externalDocs:
                  url: http://hl7.org/implement/standards/fhir/DSTU2/references-definitions.html
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
              description: Person who received the answers to the questions in the QuestionnaireResponse and recorded them in the system.
              $ref: "#/definitions/Reference"
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.author
            authored:
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.authored
              description: The datetime this resource was last updated
              type: string
              format: date-time
            source:
              description: The person who answered the questions about the subject
              $ref: "#/definitions/Reference"
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.source
            group:
              description: A group of related questions or sub-groups. May only contain either questions or groups
              schema:
                id: group
                externalDocs:
                  url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.group
                properties:
                  group:
                    description: Subgroup for questions or additional nested groups
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
                    description: Set of questions within this group. The order of questions within the group is relevant.
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
                          description: The respondent's answer(s) to the question
                          externalDocs:
                            url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.group.question.answer
                          items:
                            description: An individual answer to a question and related attributes. May only contain a single `value[x]` attribute
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
                                description: Attachment value answer to a question
                              valueCoding:
                                type: object
                                description: Coding value answer to a question
                              valueQuantity:
                                type: object
                                description: Quantity value answer to a question
                              valueReference:
                                type: object
                                description: Reference value answer to a question
                              group:
                                $ref: "#/definitions/group"
                                description: Group for "sub-questions", questions which normally appear when certain answers are given and which collect additional details.
                                externalDocs:
                                  url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.group.question.answer.group
    responses:
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    """

    if not hasattr(request, 'json') or not request.json:
        return abort(400, 'Invalid request')

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

    questionnaire_response = QuestionnaireResponse(
        user_id=current_user().id,
        document=request.json,
    )

    db.session.add(questionnaire_response)
    db.session.commit()

    response.update({'message': 'questionnaire response saved successfully'})
    return jsonify(response)

@api.route('/present-assessment/<assessment_code>')
@oauth.require_oauth()
def present_assessment(assessment_code):
    """Request that central service present an assessment via the assessment engine

    Redirects to the first assessment engine instance that is capable of administering the requested assessment
    ---
    operationId: present_assessment
    tags:
      - QuestionnaireResponse
      - Assessment Engine 
    produces:
      - text/html
    parameters:
      - name: assessment_code
        in: path
        description: Code representing assessment to administer
        required: true
        type: string
      - name: return
        in: query
        description: Intervention URL to return to after assessment completion
        required: true
        type: string
        format: url
    responses:
      303:
        description: successful operation
        headers:
          Location:
            description: URL registered with assessment engine used to provide given assessment
            type: string
            format: url
      401:
        description: if missing valid OAuth token or bad `return` parameter

    """
    # Todo: replace with proper models
    instruments = current_app.config['INSTRUMENTS']
    clients_instruments = current_app.config['CLIENTS_INSTRUMENTS']

    if not assessment_code or not assessment_code in instruments:
        abort(404, "No matching assessment found: %s" % assessment_code)

    for client_id, instrument_urls in clients_instruments.items():
        if assessment_code in instrument_urls:
            assessment_url = instrument_urls[assessment_code]
            break
    else:
        abort(404, "No assessment available: %s" % assessment_code)


    if 'return' in request.args:
        return_url = request.args.get('return')

        # Validate return URL the same way CORS requests are
        validate_client_origin(return_url)

        current_app.logger.debug('storing session[assessment_return]: %s', return_url)
        session['assessment_return'] = return_url

    return redirect(assessment_url, code=303)

@api.route('/complete-assessment')
@oauth.require_oauth()
def complete_assessment():
    """Return to the last intervention that requested an assessment be presented

    Redirects to the URL passed to central services when present-assessment was last called (if valid) or central services home
    ---
    operationId: complete_assessment
    tags:
      - QuestionnaireResponse
      - Assessment Engine 
    produces:
      - text/html
    responses:
      303:
        description: successful operation
        headers:
          Location:
            description: URL passed to central services when present-assessment was last called (if valid) or central services home
            type: string
            format: url
      401:
        description: if missing valid OAuth token

    """

    return_url = session.pop("assessment_return", "home")

    current_app.logger.debug("assessment complete, redirect to: %s", return_url)
    return redirect(return_url, code=303)

@api.route('/auditlog', methods=('POST',))
@oauth.require_oauth()
def auditlog_addevent():
    """Add event to audit log

    API for client applications to add any event to the audit log.  The message
    will land in the same audit log as any auditable internal event, including
    recording the authenticated user making the call.

    Returns a json friendly message, i.e. {"message": "ok"}
    ---
    operationId: auditlog_addevent
    tags:
      - Central Services
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          id: message
          required:
            - message
          properties:
            message:
              type: string
              description: message text
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
              description: Result, typically "ok"
      401:
        description: if missing valid OAuth token

    """
    message = request.form.get('message')
    if not message:
        return jsonify(message="missing required 'message' in post")
    auditable_event('remote message: {0}'.format(message),
                    user_id=current_user().id)
    return jsonify(message='ok')


@api.route('/portal-wrapper-html/', methods=('OPTIONS',))
@crossdomain(origin='*')
def preflight_unprotected():
    """CORS requires preflight headers

    For in browser CORS requests, first respond to an OPTIONS request
    including the necessary Access-Control headers.

    Requires separate route for OPTIONS to avoid authorization tangles.

    """
    pass  # all work for OPTIONS done in crossdomain decorator


@api.route('/portal-wrapper-html/', defaults={'username': None})
@api.route('/portal-wrapper-html/<username>')
def portal_wrapper_html(username):
    """Returns portal wrapper for insertion at top of interventions

    Get html for the portal site UI wrapper (top-level nav elements, etc)
    This is the unauthorized version, useful prior to logging in with
    Central Services.  See `protected_portal_wrapper_html` for authorized
    version.
    ---
    tags:
      - Central Services
    operationId: getPortalWrapperHTML
    produces:
      - text/html
    parameters:
      - name: login_url
        in: query
        description:
          Location to direct login requests.  Typically an entry
          point on the intervention, to initiate OAuth dance with
          Central Services.  Inclusion of this parameter affects
          the apperance of a "login" option in the portal menu.
        required: false
        type: string
      - name: username
        in: path
        description:
          Optional username, used to personalize the header.
        required: true
        type: string
    responses:
      200:
        description:
          html for direct insertion near the top of the intervention's
          page.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient


    """
    movember_profile = ''.join((
        '//',
        current_app.config['SERVER_NAME'],
        url_for('static', filename='img/movember_profile_thumb.png'),
    ))

    # workarounds till we can call protected_portal_wrapper from portal
    user = current_user()
    if user:
        if user.image_url:
            movember_profile = user.image_url
        if not username:
            if user.first_name and user.last_name:
                username = ' '.join((user.first_name, user.last_name))
            else:
                username = user.username
    else:
        user = None

    html = render_template(
        'portal_wrapper.html',
        PORTAL=''.join(('//', current_app.config['SERVER_NAME'])),
        username=username,
        user=user,
        movember_profile=movember_profile,
        login_url=request.args.get('login_url')
    )
    resp = make_response(html)
    resp.headers.add('Access-Control-Allow-Origin', '*')
    resp.headers.add('Access-Control-Allow-Headers', 'X-Requested-With')
    return resp


@api.route('/protected-portal-wrapper-html', methods=('OPTIONS',))
@crossdomain()
def preflight():
    """CORS requires preflight headers

    For in browser CORS requests, first respond to an OPTIONS request
    including the necessary Access-Control headers.

    Requires separate route for OPTIONS to avoid authorization tangles.

    """
    pass  # all work for OPTIONS done in crossdomain decorator


@api.route('/protected-portal-wrapper-html', methods=('GET',))
@oauth.require_oauth()
@crossdomain()
def protected_portal_wrapper_html():
    """Returns portal wrapper for insertion at top of interventions

    Get html for the portal site UI wrapper (top-level nav elements, etc)
    This is the authorized version, only useful after to logging in with
    Central Services.  See `portal_wrapper_html` for the unauthorized
    version.
    ---
    tags:
      - Central Services
    operationId: getProtectedPortalWrapperHTML
    produces:
      - text/html
    responses:
      200:
        description:
          html for direct insertion near the top of the intervention's
          page.
      401:
        description: if missing valid OAuth token

    """
    movember_profile = ''.join((
        '//',
        current_app.config['SERVER_NAME'],
        url_for('static', filename='img/movember_profile_thumb.png'),
    ))

    user = current_user()
    if user.image_url:
        movember_profile = user.image_url

    html = render_template(
        'portal_wrapper.html',
        PORTAL=''.join(('//', current_app.config['SERVER_NAME'])),
        username=user.username,
        user=user,
        movember_profile=movember_profile,
    )
    return make_response(html)


@api.route('/roles', defaults={'user_id': None})
@api.route('/roles/<int:user_id>')
@oauth.require_oauth()
def roles(user_id):
    """Returns simple JSON defining system or user roles

    Returns a list of all known roles.  Users belong to one or more
    roles used to control authorization.  If a user_id is provided,
    only the list of roles that user belongs to is returned.
    ---
    tags:
      - User
    operationId: getRoles
    produces:
      - application/json
    responses:
      200:
        description:
          Returns a list of all known roles.  Users belong to one or more
          roles used to control authorization.  If a user_id is provided,
          only the list of roles that user belongs to is returned.
        schema:
          id: roles
          required:
            - name
            - description
          properties:
            name:
              type: string
              description:
                Role name, always a lower case string with no white space.
            description:
              type: string
              description: Plain text describing the role.
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id

    """
    user = current_user()
    if user_id:
        if user.id != user_id:
            current_user().check_role(permission='view', other_id=user_id)
            user = get_user(user_id)
        use_roles = user.roles
    else:
        use_roles = Role.query.all()
    results = [{'name': r.name, 'description': r.description}
            for r in use_roles]
    return jsonify(roles=results)


@api.route('/roles/<int:user_id>', methods=('PUT',))
@oauth.require_oauth()
@roles_required(ROLE.ADMIN)
def set_roles(user_id):
    """Set roles for user, returns simple JSON defining user roles

    Used to set role assignments for a user.  Include all roles
    the user should be a member of.  If a list doesn't include current
    roles for the user, the users roles will be reduced to match.

    Only the 'name' field of the roles is referenced.  Must match
    current roles in the system.

    Returns a list of all roles user belongs to after change.
    ---
    tags:
      - User
    operationId: setRoles
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          id: roles
          required:
            - name
          properties:
            name:
              type: string
              description:
                The string defining the name of each role the user should
                belong to.  Must exist as an available role in the system.
    responses:
      200:
        description:
          Returns a list of all roles user belongs to after change.
        schema:
          id: user_roles
          required:
            - name
            - description
          properties:
            name:
              type: string
              description:
                Role name, always a lower case string with no white space.
            description:
              type: string
              description: Plain text describing the role.
      400:
        description: if the request incudes an unknown role.
      401:
        description:
          if missing valid OAuth token or if the authorized user lacks
          permission to view requested user_id

    """
    user = current_user()
    if user.id != user_id:
        current_user().check_role(permission='edit', other_id=user_id)
        user = get_user(user_id)

    if not request.json or 'roles' not in request.json:
        abort(400, "Requires role list")
    requested_roles = [r['name'] for r in request.json['roles']]
    matching_roles = Role.query.filter(Role.name.in_(requested_roles)).all()
    if len(matching_roles) != len(requested_roles):
        abort(404, "One or more roles requested not available")
    user.roles = matching_roles

    # Return user's updated role list
    results = [{'name': r.name, 'description': r.description}
            for r in user.roles]
    return jsonify(roles=results)


def clinical_api_shortcut_set(patient_id, codeable_concept):
    """Helper for common code used in clincal api shortcuts"""
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user(patient_id)

    if not request.json or 'value' not in request.json:
        abort(400, "Expects 'value' in JSON")
    value = str(request.json['value']).lower()
    if value not in ('true', 'false'):
        abort(400, "Expecting boolean for 'value'") 

    truthiness = ValueQuantity(value=value, units='boolean')
    patient.save_constrained_observation(codeable_concept=codeable_concept,
                                         value_quantity=truthiness)
    return jsonify(message='ok')


def clinical_api_shortcut_get(patient_id, codeable_concept):
    """Helper for common code used in clincal api shortcuts"""
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user(patient_id)
    value_quantities = patient.fetch_values_for_concept(codeable_concept)
    if value_quantities:
        assert len(value_quantities) == 1
        return jsonify(value=value_quantities[0].value)

    return jsonify(value='unknown')
