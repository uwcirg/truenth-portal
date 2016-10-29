"""Portal view functions (i.e. not part of the API or auth)"""
import requests
from flask import current_app, Blueprint, jsonify, render_template, flash
from flask import abort, redirect, request, session, url_for
from flask_login import login_user
from flask_user import roles_required, roles_not_allowed
from flask_swagger import swagger
from flask_wtf import Form
from sqlalchemy.orm.exc import NoResultFound
from wtforms import validators, HiddenField, StringField
from datetime import datetime

from .auth import next_after_login
from ..audit import auditable_event
from .crossdomain import crossdomain
from ..models.app_text import app_text
from ..models.app_text import AboutATMA, ConsentATMA, LegalATMA, ToU_ATMA
from ..models.coredata import Coredata
from ..models.identifier import Identifier
from ..models.intervention import Intervention, INTERVENTION
from ..models.message import EmailMessage
from ..models.organization import Organization, OrganizationIdentifier, OrgTree
from ..models.role import ROLE
from ..models.user import add_anon_user, current_user, get_user, User
from ..extensions import db, oauth, user_manager
from ..system_uri import SHORTCUT_ALIAS
from ..tasks import add, post_request


portal = Blueprint('portal', __name__)


def page_not_found(e):
    return render_template('error.html', no_nav="true"), 404

def server_error(e):  # pragma: no cover
    # NB - this is only hit if app.debug == False
    # exception is automatically sent to log by framework
    return render_template('error.html'), 500

@portal.before_app_request
def debug_request_dump():
    if current_app.config.get("DEBUG_DUMP_HEADERS"):
        current_app.logger.debug(
            "{0.remote_addr} {0.method} {0.path} {0.headers}".format(request))
    if current_app.config.get("DEBUG_DUMP_REQUEST"):
        output = "{0.remote_addr} {0.method} {0.path}"
        if request.data:
            output += " {0.data}"
        if request.args:
            output += " {0.args}"
        if request.form:
            output += " {0.form}"
        current_app.logger.debug(output.format(request))

@portal.route('/intentional-error')
def intentional_error():  # pragma: no cover
    # useless method to test error handling
    5/0

@portal.route('/')
def landing():
    """landing page view function - present register / login options"""
    if current_user():
        current_app.logger.debug("landing (found user) -> next_after_login")
        return next_after_login()
    return render_template('landing.html', user=None, no_nav="true")


class ShortcutAliasForm(Form):
    shortcut_alias = StringField('Code', validators=[validators.Required()])

    def validate_shortcut_alias(form, field):
        """Custom validation to confirm an alias match"""
        if len(field.data.strip()):
            try:
                Identifier.query.filter_by(
                    system=SHORTCUT_ALIAS, value=field.data).one()
            except NoResultFound:
                raise validators.ValidationError("Code not found")


@portal.route('/go', methods=['GET', 'POST'])
def specific_clinic_entry():
    """Entry point with form to insert a coded clinic shortcut

    Invited users may start here to obtain a specific clinic assignment,
    by entering the code or shortcut alias they were given.

    Store the clinic in the session for association with the user once
    registered and redirect to the standard landing page.

    """
    form = ShortcutAliasForm(request.form)
    if not form.validate_on_submit():
        return render_template('shortcut_alias.html', form=form)

    return specific_clinic_landing(form.shortcut_alias.data)


@portal.route('/go/<string:clinic_alias>')
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

    return redirect(url_for('portal.landing'))


@portal.route('/access/<string:token>')
def access_via_token(token):
    """Limited access users enter here with special token as auth

    Tokens contain encrypted data including the user_id and timestamp
    from when it was generated.

    If the token is found to be valid, and the user_id isn't associated
    with a *privilidged* account, the behavior depends on the roles assigned
    to the token's user_id:
    * WRITE_ONLY users will be directly logged into the weak auth account
    * others will be given a chance to prove their identity

    The tokens are intended to be single use, but the business rules
    aren't clear yet. ... TODO

    """
    # Should never be here if already logged in - enforce
    #if current_user():
        #abort(500, "Already logged in - can't continue")

    # Confirm the token is valid, and not expired.
    valid_seconds = current_app.config.get(
        'TOKEN_LIFE_IN_DAYS', 30) * 24 * 3600
    is_valid, has_expired, user_id = user_manager.token_manager.verify_token(
        token, valid_seconds)
    if has_expired:
        flash('Your access token has expired.', 'error')
        return redirect(url_for('portal.landing'))
    if not is_valid:
        flash('Your access token is invalid.', 'error')
        return redirect(url_for('portal.landing'))

    # Valid token - confirm user id looks legit
    user = get_user(user_id)
    not_allowed = set([ROLE.ADMIN, ROLE.APPLICATION_DEVELOPER, ROLE.SERVICE,
                      ROLE.PROVIDER])
    has = set([role.name for role in user.roles])
    if not has.isdisjoint(not_allowed):
        abort(400, "Access URL not allowed for privileged accounts")
    if ROLE.WRITE_ONLY in has:
        # legit - log in and redirect
        auditable_event("login using access_via_token", user_id=user.id)
        session['id'] = user.id
        login_user(user)
        return next_after_login()

    # Without WRITE_ONLY, we don't log the user in, but preserve the
    # invited user id, should we need to merge associated details
    # after user proves themselves and logs in
    auditable_event("invited user entered using token, pending "
                    "registration", user_id=user.id)
    session['invited_user_id'] = user.id
    return redirect(url_for('portal.challenge_identity'))


class ChallengeIdForm(Form):
    retry_count = HiddenField('retry count', default=0)
    first_name = StringField(
        'First Name', validators=[validators.input_required()])
    last_name = StringField(
        'Last Name', validators=[validators.input_required()])
    birthdate = StringField(
        'Birthdate', validators=[validators.input_required()])


@portal.route('/challenge', methods=['GET', 'POST'])
def challenge_identity():
    user = get_user(session.get('invited_user_id', None))
    if not user:
        abort(400, "missing invited user in identity challenge")

    errorMessage = ""
    form = ChallengeIdForm(request.form)
    if not form.validate_on_submit():
        return render_template('challenge_identity.html', form=form, errorMessage=None)

    first_name = form.first_name.data
    last_name = form.last_name.data
    birthdate = datetime.strptime(form.birthdate.data, '%m-%d-%Y');


    score = user.fuzzy_match(first_name=first_name,
                             last_name=last_name,
                             birthdate=birthdate)
    if score > current_app.config.get('IDENTITY_CHALLENGE_THRESHOLD', 85):
        # identity confirmed
        email = user.email
        user.mask_email()
        db.session.commit()
        del session['invited_user_id']
        session['invited_verified_user_id'] = user.id
        return redirect(url_for('user.register', email=email))

    else:
        auditable_event("Failed identity challenge tests with values:"
                        "(first_name={}, last_name={}, birthdate={})".\
                        format(first_name, last_name, birthdate),
                        user_id=user.id)
        # very modest brute force test
        form.retry_count.data = int(form.retry_count.data) + 1
        if form.retry_count.data >= 1:
             errorMessage = "Unable to match identity"
        if form.retry_count.data > 3:
            del session['invited_user_id']
            abort(404, "User Not Found")

        return render_template('challenge_identity.html', form=form, errorMessage=errorMessage)


@portal.route('/initial-queries', methods=['GET','POST'])
def initial_queries():
    """Terms of use, initial queries view function"""
    if request.method == 'POST':
        # data submission all handled via ajax calls from initial_queries
        # template.  assume POST can only be sent when valid.
        current_app.logger.debug("POST initial_queries -> next_after_login")
        return next_after_login()

    user = current_user()
    if not user:
        # Shouldn't happen, unless user came in on a bookmark
        current_app.logger.debug("initial_queries (no user!) -> landing")
        return redirect('portal.landing')

    still_needed = Coredata().still_needed(user)
    terms, consent_agreements = None, {}
    if 'tou' in still_needed:
        response = requests.get(app_text(ToU_ATMA.name_key()))
        terms = response.text
    if 'org' in still_needed:
        for org_id in OrgTree().all_top_level_ids():
            org = Organization.query.get(org_id)
            consent_url = app_text(ConsentATMA.name_key(organization=org))
            response = requests.get(consent_url)
            if response.json:
                consent_agreements[org.id] = {
                    'asset': response.json()['asset'],
                    'agreement_url': ConsentATMA.permanent_url(
                        version=response.json()['version'],
                        generic_url=consent_url)}
            else:
                consent_agreements[org.id] = {
                    'asset': response.text, 'agreement_url': consent_url}
    return render_template(
        'initial_queries.html', user=user, terms=terms,
        consent_agreements=consent_agreements, still_needed=still_needed)

@portal.route('/home')
def home():
    """home page view function

    Present user with appropriate view dependent on roles.

    The inital flow through authentication and data collection is
    controlled by next_after_login().  Only expecting requests
    here after login and intermediate steps have been handled, and then
    only if the login didn't include a 'next' target.

    Raising server error (500) if unexpected state is found to assist in
    finding problems.

    """
    user = current_user()

    # Enforce flow - expect authorized user for this view
    if not user:
        abort (500, "unexpected lack of user in /home")

    # Enforce flow - don't expect 'next' params here
    if 'next' in session and session['next']:
        abort(500, "session['next'] found in /home for user {}".\
              format(user))

    # Enforce flow - confirm we have acquired initial data
    if not Coredata().initial_obtained(user):
        still_needed = Coredata().still_needed(user)
        abort(500, 'Missing inital data still needed: {}'.\
              format(still_needed))

    # All checks passed - present appropriate view for user role
    if user.has_role(ROLE.PROVIDER):
        return redirect(url_for('patients.patients_root'))
    interventions =\
            Intervention.query.order_by(Intervention.display_rank).all()
    return render_template('portal.html', user=user,
                           interventions=interventions)


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
@roles_not_allowed(ROLE.WRITE_ONLY)
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
    response = requests.get(app_text(LegalATMA.name_key()))
    return render_template('legal.html', content=response.text)

@portal.route('/about')
def about():
    """main TrueNTH about page"""
    about_tnth = requests.get(app_text(AboutATMA.name_key(subject='TrueNTH')))
    about_mo = requests.get(app_text(AboutATMA.name_key(subject='Movember')))
    return render_template('about.html', about_tnth=about_tnth.text,
                           about_mo=about_mo.text)

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
