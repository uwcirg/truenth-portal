"""Views for Scheduled Jobs"""
from flask import abort, jsonify, Blueprint, request
from flask import render_template, session, url_for
from flask_user import roles_required
from sqlalchemy import and_

from ..database import db
from ..extensions import celery, oauth
from ..models.role import ROLE
from ..models.scheduled_job import ScheduledJob


scheduled_job_api = Blueprint('scheduled_job_api', __name__)

@scheduled_job_api.route('/scheduled_jobs')
@roles_required(ROLE.ADMIN)
@oauth.require_oauth()
def jobs_list():
    """scheduled jobs view function, intended for admins

    Present the list of all scheduled jobs (excluding __test__celery__).
    TODO: Add new jobs, modify & inactivate existing jobs

    """
    jobs = ScheduledJob.query.filter(ScheduledJob.name != "__test_celery__").all()
    tasks = []
    for task in celery.tasks.keys():
        path = task.split('.')
        if path[0] == 'portal':
            tasks.append(path[-1])
    return render_template('scheduled_jobs_list.html', jobs=jobs, tasks=tasks)