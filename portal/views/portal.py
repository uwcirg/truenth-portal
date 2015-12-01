"""Portal view functions (i.e. not part of the API or auth)"""
import pkg_resources
from flask import current_app, Blueprint, jsonify, render_template
from flask import abort, redirect, request, session, url_for
from flask.ext.login import login_user
from flask.ext.user import roles_required
from flask_swagger import swagger

from ..audit import auditable_event
from ..models.message import EmailInvite
from ..models.role import ROLE
from ..models.user import add_anon_user, current_user, get_user, User
from ..extensions import db, oauth
from .crossdomain import crossdomain
from ..tasks import add, post_request


portal = Blueprint('portal', __name__)


@portal.route('/')
def landing():
    """landing page view function"""
    if current_user():
        return redirect('home')
    return render_template('landing.html', user=None)


@portal.route('/home')
def home():
    """home page view function"""
    user = current_user()
    if user:
        # now logged in, redirect if next was previously stored
        if 'next' in session and session['next']:
            current_app.logger.debug("redirect to session[next]: %s",
                    session['next'])
            next_url = session['next']
            del session['next']
            return redirect(next_url)
        return render_template('portal.html', user=user)
    if current_app.config['ANONYMOUS_USER_ACCOUNT']:
        user = add_anon_user()
        auditable_event("register new anonymous user", user_id=user.id)
        session['id'] = user.id
        login_user(user)
        return render_template('portal.html', user=user)

    # 'next' is optionally added as a query parameter during login
    # steps, as the redirection target after login concludes.
    # store in session to survive a multi-request login process
    if request.args.get('next', None):
        current_app.logger.debug('storing session[next]: %s',
                request.args.get('next'))
        session['next'] = request.args.get('next', None)

    return redirect(url_for('user.login'))


@portal.route('/admin')
@oauth.require_oauth()
@roles_required(ROLE.ADMIN)
def admin():
    """user admin view function"""
    # can't do list comprehension in template - prepopulate a 'rolelist'
    users = User.query.all()
    for u in users:
        u.rolelist = ', '.join([r.name for r in u.roles])
    return render_template('admin.html', users=users)


@portal.route('/invite', methods=('GET', 'POST'))
@oauth.require_oauth()
@roles_required(ROLE.PATIENT)
def invite():
    """invite other users"""
    if request.method == 'GET':
        return render_template('invite.html')

    subject = request.form.get('subject')
    body = request.form.get('body')
    recipients = request.form.get('recipients')
    user = current_user()
    email = EmailInvite(subject=subject, body=body,
            recipients=recipients, sender=user.email,
            user_id=user.id)
    email.send_message()
    db.session.add(email)
    db.session.commit()
    return redirect(url_for('.invite_sent', message_id=email.id))


@portal.route('/invite/<int:message_id>')
@oauth.require_oauth()
@roles_required(ROLE.PATIENT)
def invite_sent(message_id):
    """show invite sent"""
    message = EmailInvite.query.get(message_id)
    if not message:
        abort(404, "Message not found")
    current_user().check_role('view', other_id=message.user_id)
    return render_template('invite_sent.html', message=message)


@portal.route('/profile', defaults={'user_id': None})
@portal.route('/profile/<int:user_id>')
@oauth.require_oauth()
def profile(user_id):
    """profile view function"""
    user = current_user()
    if user_id:
        user.check_role("edit", other_id=user_id)
        user = get_user(user_id)
    return render_template('profile.html', user=user)


@portal.route('/terms-of-use')
def termsofuse():
    """terms of use view function"""
    return render_template('termsofuse.html')


@portal.route('/spec')
@crossdomain(origin='*')
def spec():
    """generate swagger friendly docs from code and comments

    View function to generate swagger formatted JSON for API
    documentation.  Pulls in a few high level values from the
    package data (see setup.py) and via flask-swagger, makes
    use of any yaml comment syntax found in application docstrings.

    Point Swagger-UI to this view for rendering

    """
    # pylint: disable=E1102, W0212
    pkg_info = pkg_resources.require("portal")[0]
    pkg_dict = dict([x.split(':', 1) for x in
                    pkg_info._get_metadata('PKG-INFO')])
    swag = swagger(current_app)
    swag['info']['version'] = pkg_dict['Version']
    swag['info']['title'] = pkg_dict['Summary']
    swag['info']['description'] = pkg_dict['Description']
    swag['info']['termsOfService'] = 'http://cirg.washington.edu'
    contact = {'name': "Clinical Informatics Research Group",
               'email': "mcjustin@uw.edu",
               'url': 'http://cirg.washington.edu'}
    swag['info']['contact'] = contact
    swag['schemes'] = ['http', 'https']

    return jsonify(swag)



@portal.route("/celery-test")
def celery_test(x=16, y=16):
    """Simple view to test asynchronous tasks via celery"""
    x = int(request.args.get("x", x))
    y = int(request.args.get("y", y))
    res = add.apply_async((x, y))
    context = {"id": res.task_id, "x": x, "y": y}
    result = "add((x){}, (y){})".format(context['x'], context['y'])
    task_id = "{}".format(context['id'])
    result_url = url_for('.celery_result', task_id=task_id)
    return jsonify(result=result, task_id=task_id, result_url=result_url)


@portal.route("/celery-result/<task_id>")
def celery_result(task_id):
    retval = add.AsyncResult(task_id).get(timeout=1.0)
    return repr(retval)


@portal.route("/post-result/<task_id>")
def post_result(task_id):
    r = post_request.AsyncResult(task_id).get(timeout=1.0)
    return jsonify(status_code=r.status_code, url=r.url, text=r.text)

