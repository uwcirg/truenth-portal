"""API view functions"""
from flask import abort, Blueprint, jsonify, make_response
from flask import current_app, render_template, request, url_for

from ..models.user import current_user, get_user, Role
from ..extensions import oauth
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

@api.route('/assessment/<int:patient_id>', methods=('POST', 'PUT'))
@oauth.require_oauth()
def assessment_set(patient_id):
    """Add a questionnaire response to a patient's record

    Submit a minimal FHIR doc in JSON format including the 'QuestionnaireResponse'
    resource type.
    ---
    operationId: addQuestionnaireResponse
    tags:
      - QuestionnaireResponse
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
                - in progress
                - completed
            subject:
              type: object
              description: The subject of the questionnaire response
              $ref: "#/definitions/Patient"
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.subject
            author:
              type: object
              description: Person who received the answers to the questions in the QuestionnaireResponse and recorded them in the system.
              $ref: "#/definitions/Patient"
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.author
            authored:
              externalDocs:
                url: http://hl7.org/implement/standards/fhir/DSTU2/questionnaireresponse-definitions.html#QuestionnaireResponse.authored
              description: The datetime this resource was last updated
              type: string
              format: date-time
            source:
              type: object
              description: The person who answered the questions about the subject
              $ref: "#/definitions/Patient"
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
    return jsonify(message={'test':True})

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
          Central Services.
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
    movember_email = ''
    movember_id = ''

    # workarounds till we can call protected_portal_wrapper from portal
    user = current_user()
    if user:
        if user.image_url:
            movember_profile = user.image_url

        if user.email:
            movember_email = user.email

        if user.id:
            movember_id = user.id

        if not username:
            username = ' '.join((user.first_name, user.last_name))
    else:
        user = None

    html = render_template(
        'portal_wrapper.html',
        PORTAL=''.join(('//', current_app.config['SERVER_NAME'])),
        username=username,
        user=user,
        movember_profile=movember_profile,
        movember_email=movember_email,
        movember_id=movember_id,
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
    movember_email = ''
    movember_id = ''

    user = current_user()
    if user.image_url:
        movember_profile = user.image_url

    if user.email:
        movember_email = user.email

    if user.id:
        movember_id = user.id

    html = render_template(
        'portal_wrapper.html',
        PORTAL=''.join(('//', current_app.config['SERVER_NAME'])),
        username=user.username,
        user=user,
        movember_profile=movember_profile,
        movember_email=movember_email,
        movember_id=movember_id
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
        roles = user.roles
    else:
        roles = Role.query.all()
    results = [{'name': r.name, 'description': r.description} for r in roles]
    return jsonify(roles=results)
