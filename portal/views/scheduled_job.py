"""Views for Scheduled Jobs"""
from flask import abort, jsonify, Blueprint, request
from flask import render_template, current_app
from flask_user import roles_required

from ..audit import auditable_event
from ..database import db
from ..extensions import oauth
from ..factories.celery import create_celery
from ..models.role import ROLE
from ..models.scheduled_job import ScheduledJob
from ..models.user import current_user


scheduled_job_api = Blueprint('scheduled_job_api', __name__)


@scheduled_job_api.route('/scheduled_jobs')
@roles_required(ROLE.ADMIN)
@oauth.require_oauth()
def jobs_list():
    """scheduled jobs view function, intended for admins

    Present the list of all scheduled jobs (excluding __test__celery__).
    TODO: Add new jobs, modify & inactivate existing jobs

    """
    celery = create_celery(current_app)
    jobs = ScheduledJob.query.filter(
        ScheduledJob.name != "__test_celery__").all()
    tasks = []
    for task in celery.tasks.keys():
        path = task.split('.')
        if path[0] == 'portal':
            tasks.append(path[-1])
    return render_template('scheduled_jobs_list.html', jobs=jobs, tasks=tasks)


@scheduled_job_api.route('/api/scheduled_job', methods=('POST',))
@roles_required(ROLE.ADMIN)
@oauth.require_oauth()
def create_job():
    try:
        job = ScheduledJob.from_json(request.json)
    except ValueError as e:
        abort(400, str(e))
    if job not in db.session:
        db.session.add(job)
    db.session.commit()
    job = db.session.merge(job)
    user_id = current_user().id
    auditable_event("scheduled job '{}' updated".format(job.name),
                    user_id=user_id, subject_id=user_id,
                    context='other')
    return jsonify(job.as_json())


@scheduled_job_api.route('/api/scheduled_job/<int:job_id>')
@roles_required(ROLE.ADMIN)
@oauth.require_oauth()
def get_job(job_id):
    job = ScheduledJob.query.get(job_id)
    if not job:
        abort(404, 'job ID not found')
    return jsonify(job.as_json())


@scheduled_job_api.route(
    '/api/scheduled_job/<int:job_id>', methods=('DELETE',))
@roles_required(ROLE.ADMIN)
@oauth.require_oauth()
def delete_job(job_id):
    job = ScheduledJob.query.get(job_id)
    if not job:
        abort(404, 'job ID not found')
    db.session.delete(job)
    db.session.commit()
    msg = "scheduled job id {} deleted".format(job_id)
    user_id = current_user().id
    auditable_event(msg, user_id=user_id, subject_id=user_id,
                    context='other')
    return jsonify(message=msg)


@scheduled_job_api.route('/api/scheduled_job/<int:job_id>/trigger')
@roles_required(ROLE.ADMIN)
@oauth.require_oauth()
def trigger_job(job_id):
    job = ScheduledJob.query.get(job_id)
    if not job:
        abort(404, 'job ID not found')
    msg = job.trigger()
    return jsonify(message=msg)
