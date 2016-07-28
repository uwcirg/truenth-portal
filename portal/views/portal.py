"""Portal view functions (i.e. not part of the API or auth)"""
import requests
#from cStringIO import StringIO 
#from lxml import etree
from flask import current_app, Blueprint, jsonify, render_template
from flask import abort, redirect, request, session, url_for
from flask_login import login_user
from flask_user import roles_required
from flask_swagger import swagger

from ..audit import auditable_event
from .crossdomain import crossdomain
from ..models.coredata import Coredata
from ..models.identifier import Identifier
from ..models.intervention import INTERVENTION
from ..models.message import EmailMessage
from ..models.organization import OrganizationIdentifier
from ..models.role import ROLE
from ..models.user import add_anon_user, current_user, get_user, User
from ..extensions import db, oauth
from ..system_uri import SHORTCUT_ALIAS
from ..tasks import add, post_request

portal = Blueprint('portal', __name__)


def page_not_found(e):
    return render_template('error.html', no_nav="true"), 404

def server_error(e):  # pragma: no cover
    # NB - this is only hit if app.debug == False
    # exception is automatically sent to log by framework
    return render_template('error.html'), 500

@portal.route('/intentional-error')
def intentional_error():  # pragma: no cover
    # useless method to test error handling
    5/0

@portal.route('/')
def landing():
    """landing page view function"""
    if current_user():
        return redirect('home')
    return render_template('landing.html', user=None, no_nav="true")


@portal.route('/clinic/<string:clinic_alias>')
def specific_clinic_landing(clinic_alias):
    """Invited users start here to obtain a specific clinic assignment

    Store the clinic in the session for association with the user once
    registered and redirect to the standard landing page.

    """
    # Shortcut aliases are registered with the organization as identifiers.
    # Confirm the requested alias exists or 404
    identifier = Identifier.query.filter_by(system=SHORTCUT_ALIAS,
                                            value=clinic_alias).first()
    if not identifier:
        current_app.logger.debug("Clinic alias not found: %s", clinic_alias)
        abort(404)

    # Expecting exactly one organization for this alias, save ID in session
    results = OrganizationIdentifier.query.filter_by(
        identifier_id=identifier.id).one()
    session['associate_clinic_id'] = results.organization_id

    return redirect('/')


@portal.route('/initial-queries', methods=('GET', 'POST'))
def initial_queries():
    if request.method == 'GET':
        return render_template('initial_queries.html', user=current_user())
    return redirect('home')


@portal.route('/home')
def home():
    """home page view function"""
    user = current_user()
    if user:
        # authorized entry point - take care of pending actions
        # present intial questions if not already obtained
        if not Coredata().initial_obtained(user):
            return redirect(url_for('portal.initial_queries'))

        # now logged in, redirect if next was previously stored
        if 'next' in session and session['next']:
            current_app.logger.debug("redirect to session[next]: %s",
                    session['next'])
            next_url = session['next']
            del session['next']
            return redirect(next_url)

        # default view depends on role
        if user.has_role(ROLE.PROVIDER):
            return redirect(url_for('patients.patients_root'))
        return render_template('portal.html', user=user,
                               interventions=INTERVENTION)

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
    return render_template('admin.html', users=users, wide_container="true")


@portal.route('/invite', methods=('GET', 'POST'))
@oauth.require_oauth()
def invite():
    """invite other users"""
    if request.method == 'GET':
        return render_template('invite.html')

    subject = request.form.get('subject')
    body = request.form.get('body')
    recipients = request.form.get('recipients')
    user = current_user()
    email = EmailMessage(subject=subject, body=body,
            recipients=recipients, sender=user.email,
            user_id=user.id)
    email.send_message()
    db.session.add(email)
    db.session.commit()
    return redirect(url_for('.invite_sent', message_id=email.id))


@portal.route('/invite/<int:message_id>')
@oauth.require_oauth()
def invite_sent(message_id):
    """show invite sent"""
    message = EmailMessage.query.get(message_id)
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

@portal.route('/profile-test', defaults={'user_id': None})
@portal.route('/profile-test/<int:user_id>')
@oauth.require_oauth()
def profile_test(user_id):
    """profile test view function"""
    user = current_user()
    if user_id:
        user.check_role("edit", other_id=user_id)
        user = get_user(user_id)
    return render_template('profile_test.html', user=user)


@portal.route('/legal')
def legal():
    """ Legal/terms of use page"""
    contentXml = requests.get('https://stg-cms.us.truenth.org/c/journal/get_latest_article_content?groupId=20182&articleId=43478', verify=False)
    encoding = contentXml.content
    contentXml.encoding = encoding
    contentXmlText = contentXml.text
#123 chars before what we need
#28 chars at the end that we don't need
    content = contentXmlText
    #content = contentXmlText[123:-28]

    #contentXmlString = StringIO(contentXml)
    #tree = etree.parse(contentXmlString)
    #tree = etree.parse(StringIO(contentXml))
    #tree = etree.fromstring(contentXmlText)
    #content = "";
    #for s in tree.xpath("//static-content"):
    #    content += s.text 
    #cdata = tree.Element('![CDATA[')
    #return render_template('legal.html', content=cdata.text)
    return render_template('legal.html', content=content)

@portal.route('/about')
def about():
    """main TrueNTH about page"""
    return render_template('about.html')

@portal.route('/explore')
def explore():
    user = current_user()
    """Explore TrueNTH page"""
    return render_template('explore.html', user=user)

@portal.route('/share-your-story')
@portal.route('/shareyourstory')
@portal.route('/shareYourStory')
def share_story():
    return redirect(url_for('static', filename='files/LivedExperienceVideo.pdf'))

@portal.route('/contact', methods=('GET', 'POST'))
def contact():
    """main TrueNTH contact page"""
    user = current_user()
    if request.method == 'GET':
        sendername = user.display_name if user else ''
        email = user.email if user else ''
        return render_template('contact.html', sendername=sendername,
                               email=email)

    sender = request.form.get('email')
    sendername = request.form.get('sendername')
    subject = u"{server} contact request: {subject}".format(
        server=current_app.config['SERVER_NAME'],
        subject=request.form.get('subject'))
    body = u"From: {sendername}<br />Email: {sender}<br /><br />{body}".format(
        sendername=sendername, sender=sender, body=request.form.get('body'))
    recipients = current_app.config['CONTACT_SENDTO_EMAIL']

    user_id = user.id if user else None
    email = EmailMessage(subject=subject, body=body,
            recipients=recipients, sender=sender, user_id=user_id)
    email.send_message()
    db.session.add(email)
    db.session.commit()
    return redirect(url_for('.contact_sent', message_id=email.id))

@portal.route('/contact/<int:message_id>')
def contact_sent(message_id):
    """show invite sent"""
    message = EmailMessage.query.get(message_id)
    if not message:
        abort(404, "Message not found")
    return render_template('contact_sent.html', message=message)

@portal.route('/questions')
def questions():
    """New user question view.  Creates anon user if none in session"""
    user = current_user()
    if not user:
        user = add_anon_user()
        db.session.commit()
        auditable_event("register new anonymous user", user_id=user.id)
        session['id'] = user.id
        login_user(user)

    return render_template('questions.html', user=user)


@portal.route('/questions_anon')
def questions_anon():
    """Anonymous questions function"""
    user = current_user()
    if not user:
        user = add_anon_user()
        db.session.commit()
        auditable_event("register new anonymous user", user_id=user.id)
        session['id'] = user.id
        login_user(user)
    return render_template('questions_anon.html', user=user,
                           interventions=INTERVENTION)


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
    swag = swagger(current_app)
    swag.update({
        "info": {
            "version": current_app.config.metadata.version,
            "title": current_app.config.metadata.summary,
            "description": current_app.config.metadata.description,
            "termsOfService": "http://cirg.washington.edu",
            "contact":{
                "name": "Clinical Informatics Research Group",
                "email": "mcjustin@uw.edu",
                "url": "http://cirg.washington.edu",
            },
        },
        "schemes":("http", "https"),
    })

    # Fix swagger docs for paths with duplicate operationIds

    # Dict of offending routes (path and method), grouped by operationId
    operations = {}

    for path, path_options in swag['paths'].items():
        for method, route in path_options.items():
            if 'operationId' not in route:
                continue

            operation_id = route['operationId']

            operations.setdefault(operation_id, [])
            operations[operation_id].append({'path':path, 'method':method})



    # Alter route-specific swagger info (using operations dict) to prevent non-unique operationId
    for operation_id, routes in operations.items():
        if len(routes) == 1:
            continue

        for route_info in routes:

            path = route_info['path']
            method = route_info['method']

            route = swag['paths'][path][method]

            parameters = []
            # Remove swagger path parameters from routes where it is optional
            for parameter in route.pop('parameters', ()):

                if parameter['in'] == 'path' and ("{%s}" % parameter['name']) not in path:
                    # Prevent duplicate operationIds by adding suffix
                    # Assume "simple" version of API route if path parameter included but not in path
                    swag['paths'][path][method]['operationId'] = "{}-simple".format(operation_id)
                    continue

                parameters.append(parameter)

            # Overwrite old parameter list
            if parameters:
                swag['paths'][path][method]['parameters'] = parameters

            # Add method as suffix to prevent duplicate operationIds on synonymous routes
            if method == 'put' or method == 'post':
                swag['paths'][path][method]['operationId'] = "{}-{}".format(operation_id, method)

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
    if request.args.get('redirect-to-result', None):
        return redirect(result_url)
    return jsonify(result=result, task_id=task_id, result_url=result_url)


@portal.route("/celery-result/<task_id>")
def celery_result(task_id):
    retval = add.AsyncResult(task_id).get(timeout=1.0)
    return repr(retval)


@portal.route("/post-result/<task_id>")
def post_result(task_id):
    r = post_request.AsyncResult(task_id).get(timeout=1.0)
    return jsonify(status_code=r.status_code, url=r.url, text=r.text)
