"""Practitioner API view functions"""
from flask import abort, jsonify, Blueprint, request
from flask import render_template, current_app, url_for
from flask_user import roles_required

from ..audit import auditable_event
from ..database import db
from ..date_tools import FHIR_datetime
from ..extensions import oauth
from ..factories.celery import create_celery
from ..models.role import ROLE
from ..models.practitioner import Practitioner
from ..models.user import current_user
from .portal import check_int


practitioner_api = Blueprint('practitioner_api', __name__, url_prefix='/api')


@practitioner_api.route('/practitioner')
@oauth.require_oauth()
def practitioner_search():
    """Obtain a bundle (list) of all matching practitioners

    Filter search on key=value pairs.

    Example search:
        /api/practitioner?first_name=Indiana&last_name=Jones

    Returns a JSON FHIR bundle of practitioners as per given search terms.
    Without any search terms, returns all practitioners known to the system.
    If search terms are provided but no matching practitioners are found,
    a 404 is returned.

    ---
    operationId: practitioner_search
    tags:
      - Practitioner
    parameters:
      - name: search_parameters
        in: query
        description:
            Search parameters (`first_name`, `last_name`)
        required: false
        type: string
    produces:
      - application/json
    responses:
      200:
        description:
          Returns a FHIR bundle of [practitioner
          resources](http://www.hl7.org/fhir/practitioner.html) in JSON.
      400:
        description:
          if invalid search param keys are used
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
      404:
        description:
          if no practitioners found for given search parameters

    """
    query = Practitioner.query
    for k, v in request.args.items():
        if k not in ('first_name', 'last_name'):
            abort(400, "only `first_name`, `last_name` search filters "
                  "are available at this time")
        if v:
            d = {k: v}
            query = query.filter_by(**d)

    practs = [p.as_fhir() for p in query]

    bundle = {
        'resourceType': 'Bundle',
        'updated': FHIR_datetime.now(),
        'total': len(practs),
        'type': 'searchset',
        'link': {
            'rel': 'self',
            'href': url_for(
                'practitioner_api.practitioner_search', _external=True),
        },
        'entry': practs,
    }

    return jsonify(bundle)


# @scheduled_job_api.route('/api/scheduled_job/<int:job_id>')
# @oauth.require_oauth()
# def get_job(job_id):
#     job = ScheduledJob.query.get(job_id)
#     if not job:
#         abort(404, 'job ID {} not found'.format(job_id))
#     return jsonify(job.as_json())


# @scheduled_job_api.route('/scheduled_job', methods=('POST',))
# @oauth.require_oauth()
# def create_job():
#     try:
#         job = ScheduledJob.from_json(request.json)
#         # POST should only allow creation of new jobs
#         if ScheduledJob.query.filter(ScheduledJob.name == job.name).count():
#             raise ValueError("{} already exists; use PUT to update".format(
#                 job))
#     except ValueError as e:
#         abort(400, str(e))
#     if job not in db.session:
#         db.session.add(job)
#     db.session.commit()
#     job = db.session.merge(job)
#     user_id = current_user().id
#     auditable_event("scheduled job '{}' updated".format(job.name),
#                     user_id=user_id, subject_id=user_id,
#                     context='other')
#     return jsonify(job.as_json())


# @scheduled_job_api.route('/api/scheduled_job/<int:job_id>', methods=('PUT',))
# @roles_required(ROLE.ADMIN)
# @oauth.require_oauth()
# def update_job(job_id):
#     check_int(job_id)
#     job = ScheduledJob.query.get(job_id)
#     if not job:
#         abort(404, 'job ID {} not found'.format(job_id))
#     try:
#         job_data = job.as_json()
#         for field in request.json:
#             job_data[field] = request.json[field]
#         job.update_from_json(job_data)
#     except ValueError as e:
#         abort(400, str(e))
#     db.session.commit()
#     job = db.session.merge(job)
#     user_id = current_user().id
#     auditable_event("scheduled job '{}' updated".format(job.name),
#                     user_id=user_id, subject_id=user_id,
#                     context='other')
#     return jsonify(job.as_json())
