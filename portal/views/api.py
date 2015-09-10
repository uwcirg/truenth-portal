"""API view functions"""
from flask import abort, Blueprint, jsonify, make_response
from flask import current_app, render_template, request, url_for

from ..models.user import current_user, get_user
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
        required: false
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
        required: false
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
        required: false
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
      - name: username
        in: path
        description:
          Optional username, used to personalize the header.
        required: false
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
    movember_profile = "".join((current_app.config['PORTAL'],
        url_for('static', filename='img/movember_profile_thumb.png')))

    # workarounds till we can call protected_portal_wrapper from portal
    user = current_user()
    if user:
        if user.image_url:
            movember_profile = user.image_url

        if not username:
            username = ' '.join((user.first_name, user.last_name))

    html = render_template(
        'portal_wrapper.html',
        PORTAL=current_app.config['PORTAL'],
        username=username,
        movember_profile=movember_profile
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
    user = current_user()

    if user.image_url:
        movember_profile = user.image_url
    else:
        movember_profile = "".join((current_app.config['PORTAL'],
            url_for('static', filename='img/movember_profile_thumb.png')))

    html = render_template(
        'portal_wrapper.html',
        PORTAL=current_app.config['PORTAL'],
        username=user.username,
        movember_profile=movember_profile
    )
    return make_response(html)
