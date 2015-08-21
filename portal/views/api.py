"""API view functions"""
from flask import abort, Blueprint, jsonify, make_response
from flask import current_app, render_template, request, url_for
from urlparse import urlparse

from ..models.user import current_user, get_user
from ..extensions import oauth

api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/me')
@oauth.require_oauth()
def me():
    """Example 'me' api method.

    returns logged in user's id, username and email in JSON

    """
    user = current_user()
    return jsonify(id=user.id, username=user.username,
                   email=user.email)


@api.route('/demographics', defaults={'uid': None})
@api.route('/demographics/<int:uid>')
@oauth.require_oauth()
def demographics(uid):
    """Access demographics as a FHIR patient resource (in JSON)

    Returns demographics for requested portal user id as a FHIR
    patient resource (http://www.hl7.org/fhir/patient.html) in JSON.
    Defaults to logged-in user if `uid` is not provided.

    Raises 401 if logged-in user lacks permission to view requested
    patient.

    """
    if uid:
        current_user().check_role(permission='view', other_id=uid)
        patient = get_user(uid)
    else:
        patient = current_user()
    return jsonify(patient.as_fhir())


@api.route('/demographics/<int:uid>', methods=('POST', 'PUT'))
@oauth.require_oauth()
def demographics_set(uid):
    """Update demographics via FHIR Resource Patient

    Submit a minimal FHIR doc in JSON format including the 'Patient'
    resource type, and any fields to set.  For example, to update
    just the first name, POST or PUT:

    {"resourceType": "Patient", "name": [ {"given": ["John"]} ] }

    Returns the updated, complete FHIR patient resource
    (http://www.hl7.org/fhir/patient.html) in JSON

    Raises 401 if logged-in user lacks permission to edit requested
    patient.

    """
    current_user().check_role(permission='edit', other_id=uid)
    patient = get_user(uid)
    if not request.json or 'resourceType' not in request.json or\
            request.json['resourceType'] != 'Patient':
        abort(400, "Requires FHIR resourceType of 'Patient'")
    patient.update_from_fhir(request.json)
    return jsonify(patient.as_fhir())


@api.route('/clinical', defaults={'uid': None})
@api.route('/clinical/<int:uid>')
@oauth.require_oauth()
def clinical(uid):
    """Access clinical data as a FHIR bundle of observations (in JSON)

    Returns clinical data for requested portal user id as a FHIR
    bundle of observations (http://www.hl7.org/fhir/observation.html)
    in JSON.  Defaults to logged-in user if `uid` is not provided.

    Raises 401 if logged-in user lacks permission to view requested
    patient.

    """
    if uid:
        current_user().check_role(permission='view', other_id=uid)
        patient = get_user(uid)
    else:
        patient = current_user()
    return jsonify(patient.clinical_history(requestURL=request.url))


@api.route('/clinical/<int:uid>', methods=('POST', 'PUT'))
@oauth.require_oauth()
def clinical_set(uid):
    """Add clinical entry via FHIR Resource Observation

    Submit a minimal FHIR doc in JSON format including the 'Observation'
    resource type, and any fields to retain.  NB, only a subset
    are persisted in the portal including {"name"(CodeableConcept),
    "valueQuantity", "status", "issued"} - others will be ignored.

    Returns a json friendly message, i.e. {"message": "ok"}

    Raises 401 if logged-in user lacks permission to edit requested
    patient.

    """
    current_user().check_role(permission='edit', other_id=uid)
    patient = get_user(uid)
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
    """Returns portal wrapper for insertion at top of interventions"""
    movember_profile = "".join((current_app.config['PORTAL'],
        url_for('static', filename='img/movember_profile_thumb.png')))
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
def pre_flight_portal_wrapper():
    """For in browser requests - first need to communicate via OPTIONS

    oauth protected views served to the browser require an OPTIONS
    view function with Access-Control headers, as a pre-flight check
    before the protected GET request is made.

    """
    resp = make_response()

    # TODO: validate the referrer is really someone we trust
    # either by use of whitelist, or perhaps just a similar URL
    # in clients._redirect_uris
    ref = request.referrer
    if ref:
        parsed = urlparse(ref)
        origin = '{uri.scheme}://{uri.netloc}'.format(uri=parsed)
        resp.headers.add('Access-Control-Allow-Origin', origin)
    resp.headers.add('Access-Control-Allow-Credentials', 'true')
    resp.headers.add('Access-Control-Allow-Headers',
            'Authorization, X-Requested-With')
    return resp


@api.route('/protected-portal-wrapper-html')
@oauth.require_oauth()
def protected_portal_wrapper_html():
    """Returns portal wrapper for insertion at top of interventions

    Protected version of the 'portal_wrapper_html API function - only
    functional with valid oauth token

    """
    user = current_user()
    username = ' '.join((user.first_name, user.last_name))

    if user.image_url:
        movember_profile = user.image_url
    else:
        movember_profile = "".join((current_app.config['PORTAL'],
            url_for('static', filename='img/movember_profile_thumb.png')))

    html = render_template(
        'portal_wrapper.html',
        PORTAL=current_app.config['PORTAL'],
        username=username,
        movember_profile=movember_profile
    )
    resp = make_response(html)
    resp.headers.add('Access-Control-Allow-Origin', 'http://truenth-intervention-demo.cirg.washington.edu:8000')
    resp.headers.add('Access-Control-Allow-Credentials', 'true')
    resp.headers.add('Access-Control-Allow-Headers', 'X-Requested-With')
    return resp
