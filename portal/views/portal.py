"""Portal view functions (i.e. not part of the API or auth)"""

from datetime import datetime
from pprint import pformat
from time import strftime, time
import sys
from urllib.parse import urlencode

from celery.exceptions import TimeoutError
from celery.result import AsyncResult
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    render_template_string,
    request,
    safe_join,
    session,
    send_from_directory,
    url_for,
)
from flask_babel import gettext as _
from flask_sqlalchemy import get_debug_queries
from flask_swagger import swagger
from flask_user import roles_required
from flask_wtf import FlaskForm
from sqlalchemy import and_
from sqlalchemy.orm.exc import NoResultFound
from wtforms import (
    BooleanField,
    HiddenField,
    IntegerField,
    StringField,
    validators,
)

from ..audit import auditable_event
from ..database import db
from ..date_tools import FHIR_datetime
from ..extensions import oauth
from ..factories.celery import create_celery
from ..models.app_text import (
    AppText,
    InitialConsent_ATMA,
    MailResource,
    UndefinedAppText,
    UserInviteEmail_ATMA,
    UserReminderEmail_ATMA,
    VersionedResource,
    app_text,
    get_terms,
)
from ..models.client import validate_origin
from ..models.communication import Communication, load_template_args
from ..models.coredata import Coredata
from ..models.fhir import bundle_results
from ..models.i18n import get_locale
from ..models.identifier import Identifier
from ..models.login import login_user
from ..models.message import EmailMessage
from ..models.next_step import NextStep
from ..models.organization import (
    Organization,
    OrganizationIdentifier,
    OrgTree,
    UserOrganization,
)
from ..models.qb_timeline import invalidate_users_QBT
from ..models.questionnaire_response import QuestionnaireResponse
from ..models.research_study import EMPRO_RS_ID, ResearchStudy
from ..models.role import ALL_BUT_WRITE_ONLY, ROLE
from ..models.table_preference import TablePreference
from ..models.url_token import BadSignature, SignatureExpired, verify_token
from ..models.user import User, current_user, get_user, unchecked_get_user
from ..system_uri import SHORTCUT_ALIAS
from ..timeout_lock import TimeoutLock
from ..trace import dump_trace, establish_trace, trace
from ..type_tools import check_int
from .auth import logout, next_after_login
from .crossdomain import crossdomain

portal = Blueprint('portal', __name__)


@portal.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='img/favicon.ico'), code=302)


@portal.route('/no-script')
def no_script():
    return make_response(_("This application requires Javascript enabled."
                           " Please check your browser settings."))


@portal.before_app_request
def assert_locale_selector():
    g.start_request_time = time()
    # Confirm import & use of custom babel localeselector function.
    # Necessary to import get_locale to bring into the request scope to
    # prevent the default babel locale selector from being used.
    locale_code = get_locale()

    # assign locale code as global for easy access in template
    if locale_code:
        g.locale_code = locale_code


@portal.before_app_request
def debug_request_dump():
    if current_app.config.get("DEBUG_DUMP_HEADERS"):
        current_app.logger.debug(
            "{0.remote_addr} {0.method} {0.path} {0.headers}".format(request))
    if current_app.config.get("DEBUG_DUMP_REQUEST"):
        output = "{0.remote_addr} {0.method} {0.path}"
        if request.data:
            output += " {data}"
        if request.args:
            output += " {0.args}"
        if request.form:
            output += " {0.form}"
        current_app.logger.debug(output.format(
            request,
            data=request.get_data(as_text=True),
        ))


@portal.after_app_request
def report_slow_queries(response):
    """Log slow database queries

    This will only function if BOTH values are set in the config:
        DATABASE_QUERY_TIMEOUT = 0.5  # threshold in seconds
        SQLALCHEMY_RECORD_QUERIES = True

    """
    if current_app.config.get("LOG_SLOW_RESPONSES"):
        if not hasattr(g, 'start_request_time'):
            return response
        duration = time() - g.start_request_time
        if duration > 5.0:
            current_app.logger.warning("{} took {}".format(
                request.url, duration))
        elif duration > 0.5:
            current_app.logger.debug("{} took {}".format(
                request.url, duration))

    threshold = current_app.config.get('DATABASE_QUERY_TIMEOUT')
    if threshold:
        for query in get_debug_queries():
            if query.duration >= threshold:
                current_app.logger.warning(
                    "SLOW QUERY: {0.statement}\n"
                    "Duration: {0.duration:.4f} seconds\n"
                    "Parameters: {0.parameters}\n"
                    "Context: {0.context}".format(query))
    return response


@portal.route('/report-error')
@oauth.require_oauth()
def report_error():
    """Useful from front end, client-side to raise attention to problems

    On occasion, an exception will be generated in the front end code worthy of
    gaining attention on the server side.  By making a GET request here, a
    server side error will be generated (encouraging the system to handle it
    as configured, such as by producing error email).

    OAuth protected to prevent abuse.

    Any of the following query string arguments (and their values) will be
    included in the exception text, to better capture the context.  None are
    required.

    :subject_id: User on which action is being attempted
    :message: Details of the error event
    :page_url: The page requested resulting in the error

    actor_id need not be sent, and will always be included - the OAuth
    protection guarentees and defines a valid current user.

    """
    message = {'actor': "{}".format(current_user())}
    accepted = ('subject_id', 'page_url', 'message')
    for attr in accepted:
        value = request.args.get(attr)
        if value:
            message[attr] = value

    # log as an error message - but don't raise a server error
    # for the front end to manage.
    current_app.logger.error("Received error {}".format(pformat(message)))
    return jsonify(error='received')


class ShortcutAliasForm(FlaskForm):
    shortcut_alias = StringField(
        'Code', validators=[validators.DataRequired()])

    @staticmethod
    def validate_shortcut_alias(field):
        """Custom validation to confirm an alias match"""
        if len(field.data.strip()):
            try:
                Identifier.query.filter_by(
                    system=SHORTCUT_ALIAS, _value=field.data).one()
            except NoResultFound:
                raise validators.ValidationError("Code not found")


@portal.route('/substudy-tailored-content')
@oauth.require_oauth()
def substudy_tailored_content():
    return send_from_directory(
        safe_join(current_app.static_folder, 'templates'),
        'substudy_tailored_content.html',
        cache_timeout=-1
    )

@portal.route('/go', methods=['GET', 'POST'])
def specific_clinic_entry():
    """Entry point with form to insert a coded clinic shortcut

    Invited users may start here to obtain a specific clinic assignment,
    by entering the code or shortcut alias they were given.

    Store the clinic in the session for association with the user once
    registered and redirect to the standard landing page.

    NB if already logged in - this will bounce user to home

    """
    if current_user():
        if current_app.config.get('GIL'):
            return redirect(url_for('gil.home'))
        else:
            return redirect(url_for('eproms.home'))

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
                                            _value=clinic_alias).first()
    if not identifier:
        current_app.logger.debug("Clinic alias not found: %s", clinic_alias)
        abort(404)

    # Expecting exactly one organization for this alias, save ID in session
    results = OrganizationIdentifier.query.filter_by(
        identifier_id=identifier.id).one()

    # Top-level orgs with child orgs won't work, as the UI only lists
    # the clinic level
    org = Organization.query.get(results.organization_id)
    if org.partOf_id is None:
        orgs = OrgTree().here_and_below_id(results.organization_id)
        for childOrg in orgs:
            # the org tree contains an org other than the alias org itself
            if childOrg != results.organization_id:
                abort(400, "alias points to top-level organization")

    session['associate_clinic_id'] = results.organization_id
    current_app.logger.debug(
        "Storing session['associate_clinic_id']{}".format(
            session['associate_clinic_id']))

    return redirect(url_for('user.register'))


@portal.route('/require_cookies')
def require_cookies():
    """give front end opportunity to verify cookies

    Renders HTML including cookie check, then redirects back to `target`
    NB - query string 'cookies_tested=True' added to target for client
    to confirm this process happened.

    """
    mutable_args = request.args.copy()
    target = mutable_args.pop('target')
    if not target:
        raise ValueError("require cookies needs a `target`")

    mutable_args['cookies_tested'] = True
    query_string = urlencode(mutable_args)
    delimiter = '&' if '?' in target else '?'
    target = "{}{}{}".format(target, delimiter, query_string)

    return render_template('require_cookies.html', target=target)


@portal.route('/access/<string:token>', defaults={'next_step': None})
@portal.route('/access/<string:token>/<string:next_step>')
def access_via_token(token, next_step=None):
    """Limited access users enter here with special token as auth

    Tokens contain encrypted data including the user_id and timestamp
    from when it was generated.

    If the token is found to be valid, and the user_id isn't associated
    with a *privileged* account, the behavior depends on the roles assigned
    to the token's user_id:
    * WRITE_ONLY users will be directly logged into the weak auth account
    * others will be given a chance to prove their identity

    :param next_step: if the user is to be redirected following validation
        and intial queries, include a value.  These come from a controlled
        vocabulary - see `NextStep`

    """
    # logout current user if one is logged in.
    if current_user():
        logout(prevent_redirect=True, reason="forced from /access_via_token")
        assert (not current_user())

    # Confirm the token is valid, and not expired.
    valid_seconds = current_app.config.get(
        'TOKEN_LIFE_IN_DAYS') * 24 * 3600
    try:
        user_id = verify_token(token, valid_seconds)
    except SignatureExpired:
        current_app.logger.info("token access failed: "
                                "expired token {}".format(token))
        abort(404, "URL token has expired")
    except BadSignature:
        abort(404, "URL token is invalid")

    # Valid token - confirm user id looks legit
    user = unchecked_get_user(user_id)
    not_allowed = {
        ROLE.ADMIN.value,
        ROLE.APPLICATION_DEVELOPER.value,
        ROLE.SERVICE.value}
    has = {role.name for role in user.roles}
    if not has.isdisjoint(not_allowed):
        abort(400, "Access URL not allowed for privileged accounts")

    # if provided, validate and store target in session
    if next_step:
        NextStep.validate(next_step)
        target_url = getattr(NextStep, next_step)(user)
        if not target_url:
            # Due to access strategies, the next step may not (yet) apply
            abort(400,
                  "Patient doesn't qualify for '{}', can't continue".format(
                      next_step))
        session['next'] = target_url
        current_app.logger.debug(
            "/access with next_step, storing in session['next']: {}".format(
                session['next']))

    # as this is the entry point for many pre-registered or not-yet-logged-in
    # users, capture their locale_code in the session for template rendering
    # prior to logging in.  (Post log-in, the current_user().locale_code is
    # always available
    session['locale_code'] = user.locale_code

    if {ROLE.WRITE_ONLY.value, ROLE.ACCESS_ON_VERIFY.value}.intersection(has):
        # write only users with special role skip the challenge protocol
        if ROLE.PROMOTE_WITHOUT_IDENTITY_CHALLENGE.value in has:

            # access_on_verify users are REQUIRED to verify
            if ROLE.ACCESS_ON_VERIFY.value in has:
                current_app.logger.error(
                    "ACCESS_ON_VERIFY {} has disallowed role "
                    "PROMOTE_WITHOUT_IDENTITY_CHALLENGE".format(user))
                abort(400, "Invalid state - access denied")

            # only give such tokens 5 minutes - recheck validity
            verify_token(token, valid_seconds=5 * 60)
            auditable_event("promoting user without challenge via token, "
                            "pending registration", user_id=user.id,
                            subject_id=user.id, context='account')
            user.mask_email()
            db.session.commit()
            session['invited_verified_user_id'] = user.id
            return redirect(url_for('user.register', email=user.email))

        # If user does not have PROMOTE_WITHOUT_IDENTITY_CHALLENGE,
        # challenge the user identity, followed by a redirect to the
        # appropriate page.
        session['challenge.user_id'] = user.id
        if not all((user.birthdate, user.first_name, user.last_name)):
            current_app.logger.error(
                "{} w/o all (birthdate, first_name, last_name); can't "
                "verify".format(user))
            abort(400, "invalid state - can't continue")

        if ROLE.ACCESS_ON_VERIFY.value in has:
            # Send user to verify, and then follow post login flow
            session['challenge.access_on_verify'] = True
            session['challenge.next_url'] = url_for('auth.next_after_login')
        else:
            # Still here implies a WRITE_ONLY user in process of registration.
            # Preserve the invited user id, should we need to
            # merge associated details after user proves themselves and logs in
            auditable_event(
                "invited user entered using token, pending registration",
                user_id=user.id, subject_id=user.id, context='account')
            session['challenge.next_url'] = url_for(
                'user.register', email=user.email)
            session['challenge.merging_accounts'] = True
        return redirect(
            url_for('portal.challenge_identity', request_path=request.url))

    # If not WRITE_ONLY user, redirect to login page
    # Email field is auto-populated unless using alt auth (fb/google/etc)
    if user.email and user.password:
        if (
                current_app.config.get('ENABLE_URL_AUTHENTICATED') and
                Coredata().initial_obtained(user)):
            # TN-2627, allow completion of PROMs w/o authentication
            login_user(user=user, auth_method='url_authenticated')
            return next_after_login()

        return redirect(url_for('user.login', email=user.email))
    return redirect(url_for('user.login'))


class ChallengeIdForm(FlaskForm):
    retry_count = HiddenField('retry count', default=0)
    next_url = HiddenField('next')
    user_id = HiddenField('user')
    merging_accounts = HiddenField('merging_accounts')
    access_on_verify = HiddenField('access_on_verify')
    first_name = StringField(
        'First Name', validators=[validators.input_required()])
    last_name = StringField(
        'Last Name', validators=[validators.input_required()])
    birthdate = StringField(
        'Birthdate', validators=[validators.input_required()])


@portal.route('/challenge', methods=['GET', 'POST'])
def challenge_identity(
        user_id=None, next_url=None, merging_accounts=False,
        access_on_verify=False, request_path=None):
    """Challenge the user to verify themselves

    Can't expose the parameters for security reasons - use the session,
    namespace each variable i.e. session['challenge.user_id'] unless
    calling as a function.

    :param user_id: the user_id to verify - invited user or the like
    :param next_url: destination url on successful challenge completion
    :param merging_accounts: boolean value, set true IFF on success, the
        user account will be merged into a new account, say from a weak
        authenicated WRITE_ONLY invite account
    :param access_on_verify: boolean value, set true IFF on success, the
        user should be logged in once validated, i.e. w/o a password
    :param request_path: the requested url prior to redirection to here
        necessary in no cookie situations, to redirect user back

    """
    # At this point, we can expect a session, or the user likely
    # doesn't have cookies enabled.  (ignore misleading `_fresh`
    # and `_permanent` keys)
    session_keys = [k for k in session if k not in ('_fresh', '_permanent')]
    if not session_keys:
        request_path = request.args.get('request_path', request_path)
        current_app.logger.warning(
            "failed request due to lack of cookies: {}".format(request_path))
        return redirect(url_for(
            'portal.require_cookies', target=request_path))

    if request.method == 'GET':
        # Pull parameters from session if not defined
        if not (user_id and next_url):
            user_id = session.get('challenge.user_id')
            next_url = session.get('challenge.next_url')
            merging_accounts = session.get(
                'challenge.merging_accounts', False)
            access_on_verify = session.get(
                'challenge.access_on_verify', False)

    if request.method == 'POST':
        form = ChallengeIdForm(request.form)
        if form.next_url.data:
            validate_origin(form.next_url.data)
        if not form.user_id.data:
            abort(400, "missing user in identity challenge")
        user = unchecked_get_user(form.user_id.data)
    else:
        user = unchecked_get_user(user_id)
        form = ChallengeIdForm(
            next_url=next_url, user_id=user.id,
            merging_accounts=merging_accounts,
            access_on_verify=access_on_verify)

    error = ""
    if not form.validate_on_submit():
        return render_template(
            'challenge_identity.html', form=form, errorMessage=error)

    first_name = form.first_name.data
    last_name = form.last_name.data
    try:
        birthdate = datetime.strptime(form.birthdate.data, '%m-%d-%Y')
    except ValueError as ve:
        current_app.logger.warning(
            "failed challenge birthdate format, {}".format(ve))
        birthdate = None

    score = user.fuzzy_match(first_name=first_name,
                             last_name=last_name,
                             birthdate=birthdate)

    if score < current_app.config.get('IDENTITY_CHALLENGE_THRESHOLD', 85):
        auditable_event(
            "Failed identity challenge tests with values:"
            "(first_name={}, last_name={}, birthdate={})".format(
                first_name, last_name, birthdate),
            user_id=user.id, subject_id=user.id,
            context='authentication')
        # very modest brute force test
        form.retry_count.data = int(form.retry_count.data) + 1
        if form.retry_count.data >= 1:
            error = _("Unable to match identity")
        if form.retry_count.data > 3:
            abort(404, _("User Not Found"))

        return render_template(
            'challenge_identity.html', form=form, errorMessage=error)

    # identity confirmed
    session['challenge_verified_user_id'] = user.id
    if form.merging_accounts.data == 'True':
        user.mask_email()
        db.session.commit()
        session['invited_verified_user_id'] = user.id
    if form.access_on_verify.data == 'True':
        # Log user in as they have now verified
        login_user(user=user, auth_method='url_authenticated_and_verified')
    return redirect(form.next_url.data)


@portal.route('/confirm-identity', methods=['GET', 'POST'])
def confirm_identity():
    return render_template(
        'confirm_identity.html', user=current_user(),
        redirect_url=request.args.get("redirect_url", "/"))

@portal.route('/initial-queries', methods=['GET', 'POST'])
def initial_queries():
    """Initial consent terms, initial queries view function"""
    user = get_user(current_user().id, 'edit')
    if not user:
        # Shouldn't happen, unless user came in on a bookmark
        current_app.logger.debug("initial_queries (no user!) -> landing")
        return redirect('/')
    if user.deleted:
        abort(400, "deleted user - operation not permitted")
    if request.method == 'POST':
        """
        data submission all handled via ajax calls from initial_queries
        template.  assume POST can only be sent when valid.
        """
        current_app.logger.debug("POST initial_queries -> next_after_login")
        return next_after_login()
    elif len(Coredata().still_needed(user)) == 0:
        # also handle the situations that resulted from:
        #  1. user refreshing the browser or
        #  2. exiting browser and resuming session thereafter
        # In both cases, the request method is GET, hence a redirect back to
        # initial-queries page won't ever reach the above check specifically
        # for next_after_login based on the request method of POST
        current_app.logger.debug("GET initial_queries -> next_after_login")
        return next_after_login()

    org = user.first_top_organization()
    role = None
    for r in (ROLE.STAFF_ADMIN.value, ROLE.STAFF.value, ROLE.PATIENT.value):
        if user.has_role(r):
            # treat staff_admins as staff for this lookup
            r = ROLE.STAFF.value if r == ROLE.STAFF_ADMIN.value else r
            role = r
    terms = get_terms(user.locale_code, org, role)
    substudy_terms = None
    enrolled_in_substudy = EMPRO_RS_ID in ResearchStudy.assigned_to(user)
    if enrolled_in_substudy:
        substudy_terms = get_terms(locale_code=user.locale_code, org=org,
                                   role=role, research_study_id=EMPRO_RS_ID)

    # need this at all time now for ui
    consent_agreements = Organization.consent_agreements(
        locale_code=user.locale_code)

    return render_template(
        'initial_queries.html', user=user, terms=terms,
        substudy_terms=substudy_terms,
        consent_agreements=consent_agreements)


@portal.route('/admin')
@roles_required(ROLE.ADMIN.value)
@oauth.require_oauth()
def admin():
    """user admin view function"""
    # can't do list comprehension in template - prepopulate a 'rolelist'

    user = get_user(current_user().id, 'edit')

    pref_org_list = None
    # check user table preference for organization filters
    pref = TablePreference.query.filter_by(table_name='adminList',
                                           user_id=user.id).first()
    if pref and pref.filters:
        pref_org_list = pref.filters.get('orgs_filter_control')

    if pref_org_list:
        org_list = set()

        # for selected filtered orgs, we also need to get the children
        # of each, if any
        for orgId in pref_org_list:
            check_int(orgId)
            if orgId == 0:  # None of the above doesn't count
                continue
            org_list.update(OrgTree().here_and_below_id(orgId))

        users = User.query.join(UserOrganization).filter(and_(
            User.deleted_id.is_(None),
            UserOrganization.user_id == User.id,
            UserOrganization.organization_id != 0,
            UserOrganization.organization_id.in_(org_list)))
    else:
        org_list = Organization.query.all()
        users = User.query.filter_by(deleted=None).all()

    return render_template(
        'admin/admin.html', users=users, wide_container="true",
        org_list=list(org_list), user=user)


@portal.route('/invite', methods=('GET', 'POST'))
@oauth.require_oauth()
def invite():
    """invite other users via form data

    see also /api/user/{user_id}/invite

    """
    if request.method == 'GET':
        return render_template('invite.html')

    subject = request.form.get('subject')
    body = request.form.get('body')
    recipients = request.form.get('recipients')
    user = get_user(current_user().id, 'view')
    if not user.email:
        abort(400, "Users without an email address can't send email")
    email = EmailMessage(
        subject=subject, body=body, recipients=recipients,
        sender=user.email, user_id=user.id)
    email.send_message()
    db.session.add(email)
    db.session.commit()
    return invite_sent(message_id=email.id)


@portal.route('/invite/<int:message_id>')
@oauth.require_oauth()
def invite_sent(message_id):
    """show invite sent"""
    message = EmailMessage.query.get(message_id)
    if not message:
        abort(404, "Message not found")
    get_user(message.user_id, 'view')
    return render_template('invite_sent.html', message=message)


@portal.route('/profile', defaults={'user_id': None})
@portal.route('/profile/<int:user_id>')
@roles_required(ALL_BUT_WRITE_ONLY)
@oauth.require_oauth()
def profile(user_id):
    """profile view function"""
    # template file for view of other user's profile
    template_file = 'profile/user_profile.html'

    if user_id is None:
        user_id = current_user().id
        # template file for user self's profile
        template_file = 'profile/my_profile.html'

    user = get_user(user_id, "edit")
    consent_agreements = Organization.consent_agreements(
        locale_code=user.locale_code)
    terms = VersionedResource(
        app_text(InitialConsent_ATMA.name_key()),
        locale_code=user.locale_code)

    return render_template(template_file, user=user, terms=terms,
                           current_user=current_user(),
                           consent_agreements=consent_agreements)


@portal.route(
    '/patient-invite-email/<int:user_id>', defaults={'research_study_id': 0})
@portal.route('/patient-invite-email/<int:user_id>/<int:research_study_id>')
@roles_required([ROLE.ADMIN.value, ROLE.STAFF_ADMIN.value, ROLE.STAFF.value])
@oauth.require_oauth()
def patient_invite_email(user_id, research_study_id):
    """Patient Invite Email Content"""
    user = get_user(user_id, 'edit')

    try:
        top_org = user.first_top_organization()
        if top_org:
            name_key = UserInviteEmail_ATMA.name_key(
                org=top_org.name,
                research_study_id=research_study_id)
        else:
            name_key = UserInviteEmail_ATMA.name_key(
                research_study_id=research_study_id
            )
        args = load_template_args(user=user)
        item = MailResource(
            app_text(name_key), locale_code=user.locale_code, variables=args)
    except UndefinedAppText:
        """return no content and 204 no content status"""
        return '', 204

    return jsonify(subject=item.subject, body=item.body)


@portal.route('/patient-reminder-email/<int:user_id>')
@roles_required([ROLE.ADMIN.value, ROLE.STAFF_ADMIN.value, ROLE.STAFF.value])
@oauth.require_oauth()
def patient_reminder_email(user_id):
    """Patient Reminder Email Content

    Query string
    :param research_study_id: set for targeted reminder emails, defaults to 0

    """
    from ..models.qb_status import QB_Status
    user = get_user(user_id, 'edit')
    research_study_id = int(request.args.get('research_study_id', 0))
    try:
        top_org = user.first_top_organization()
        if top_org:
            # TODO lookup sub-study specific email content
            #  if research_study_id == 1
            name_key = UserReminderEmail_ATMA.name_key(org=top_org.name)
        else:
            name_key = UserReminderEmail_ATMA.name_key()

        # If the user has a pending questionnaire bank, include for due date
        qstats = QB_Status(
            user,
            research_study_id=research_study_id,
            as_of_date=datetime.utcnow())
        qbd = qstats.current_qbd()
        if qbd:
            qb_id, qb_iteration = qbd.qb_id, qbd.iteration
        else:
            qb_id, qb_iteration = None, None

        args = load_template_args(
            user=user, questionnaire_bank_id=qb_id, qb_iteration=qb_iteration)
        item = MailResource(
            app_text(name_key), locale_code=user.locale_code, variables=args)
    except UndefinedAppText:
        """return no content and 204 no content status"""
        return '', 204

    return jsonify(subject=item.subject, body=item.body)


@portal.route('/share-your-story')
@portal.route('/shareyourstory')
@portal.route('/shareYourStory')
def share_story():
    return redirect(
        url_for('static', filename='files/LivedExperienceVideo.pdf'))


@portal.route('/robots.txt')
def robots():
    if current_app.config["SYSTEM_TYPE"].lower() == "production":
        return "User-agent: * \nAllow: /"
    return "User-agent: * \nDisallow: /"


@portal.route('/contact/<int:message_id>')
def contact_sent(message_id):
    """show invite sent"""
    message = EmailMessage.query.get(message_id)
    if not message:
        abort(404, "Message not found")
    return render_template('contact_sent.html', message=message)


@portal.route('/psa-tracker')
def psa_tracker():
    user = current_user()
    if user:
        get_user(user.id, "edit")
    return render_template('psa_tracker.html', user=user)


class SettingsForm(FlaskForm):
    timeout = IntegerField(
        'Session Timeout for This Web Browser (in seconds)',
        validators=[validators.DataRequired()])
    patient_id = IntegerField(
        'Patient to edit', validators=[validators.optional()])
    timestamp = StringField(
        "Datetime string for patient's questionnaire_responses, "
        "format YYYY-MM-DD")
    import_orgs = BooleanField('Import Organizations from Site Persistence')


@portal.route('/settings', methods=['GET', 'POST'])
@roles_required(ROLE.ADMIN.value)
@oauth.require_oauth()
def settings():
    """settings panel for admins"""
    # load all top level orgs and consent agreements
    user = get_user(current_user().id, 'view')
    organization_consents = Organization.consent_agreements(
        locale_code=user.locale_code)

    # load all app text values - expand when possible
    apptext = {}
    for a in AppText.query.all():
        try:
            # expand strings with just config values, such as LR
            apptext[a.name] = app_text(a.name)
        except ValueError:
            # lack context to expand, show with format strings
            apptext[a.name] = a.custom_text

    default_timeout = current_app.config['DEFAULT_INACTIVITY_TIMEOUT']
    current_timeout = request.cookies.get("SS_TIMEOUT", default_timeout)
    form = SettingsForm(request.form, timeout=current_timeout)
    if not form.validate_on_submit():
        return render_template(
            'settings.html',
            form=form,
            apptext=apptext,
            organization_consents=organization_consents,
            wide_container="true")

    if form.import_orgs.data:
        from ..config.model_persistence import ModelPersistence
        establish_trace("Initiate import...")
        try:
            org_persistence = ModelPersistence(
                model_class=Organization, sequence_name='organizations_id_seq',
                lookup_field='id')
            org_persistence.import_(keep_unmentioned=False, target_dir=None)
        except ValueError as e:
            trace("IMPORT ERROR: {}".format(e))

        # Purge cached data and reload.
        OrgTree().invalidate_cache()
        organization_consents = Organization.consent_agreements(
            locale_code=user.locale_code)

    response = make_response(render_template(
        'settings.html',
        form=form,
        apptext=apptext,
        organization_consents=organization_consents,
        trace_data=dump_trace(),
        wide_container="true"))

    # Only retain custom timeout if set different from default
    if form.timeout.data != default_timeout:
        if form.timeout.data > current_app.config.get(
                'PERMANENT_SESSION_LIFETIME'):
            abort(400, "Inactivity timeout value can't exceed"
                       " PERMANENT_SESSION_LIFETIME")
        # set cookie max_age to 5 years for config retention
        max_age = 60 * 60 * 24 * 365 * 5
        response.set_cookie(
            'SS_TIMEOUT', str(form.timeout.data), max_age=max_age)
    return response


@portal.route('/api/settings', defaults={'config_key': None})
@portal.route('/api/settings/<string:config_key>')
def config_settings(config_key):
    # return selective keys - not all can be be viewed by users, e.g.secret key
    config_prefix_whitelist = (
        'ACCEPT_TERMS_ON_NEXT_ORG',
        'CONSENT',
        'COPYRIGHT',
        'GIL',
        'LOCALIZED_AFFILIATE_ORG',
        'LR_',
        'MAINTENANCE_',
        'PROTECTED_FIELDS',
        'PROTECTED_ORG',
        'PATIENT_LIST_ADDL_FIELDS',
        'REQUIRED_CORE_DATA',
        'PRE_REGISTERED_ROLES',
        'SHOW_PROFILE_MACROS',
        'SYSTEM',
    )
    if config_key:
        key = config_key.upper()
        if not any(
            key.startswith(prefix) for prefix in config_prefix_whitelist
        ):
            abort(400, "Configuration key '{}' not available".format(key))
        return jsonify({key: current_app.config.get(key)})
    config_settings = {}
    # return selective keys - not all can be be viewed by users, e.g.secret key
    for key in current_app.config:
        if any(key.startswith(prefix) for prefix in config_prefix_whitelist):
            config_settings[key] = current_app.config.get(key)
    return jsonify(config_settings)


@portal.route('/research')
@roles_required([ROLE.RESEARCHER.value])
@oauth.require_oauth()
def research_dashboard():
    """Research Dashboard

    Only accessible to those with the Researcher role.

    """
    user = get_user(current_user().id, 'view')
    return render_template('research.html', user=user)


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
    metadata = current_app.config.metadata
    swag.update({
        "info": {
            "version": metadata['version'],
            "title": metadata['summary'],
            "termsOfService": metadata['home-page'],
            "contact": {
                "name": metadata['author'],
                "email": metadata['author-email'],
                "url": metadata['home-page'],
            },
        },
        "schemes": (current_app.config['PREFERRED_URL_SCHEME'],),
        "securityDefinitions": {
            "ServiceToken": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
            },
            "OAuth2AuthzFlow": {
                "type": "oauth2",
                "authorizationUrl": url_for('auth.authorize', _external=True),
                "tokenUrl": url_for('auth.access_token', _external=True),
                "flow": "accessCode",
                "scopes": {},
            }
        },
    })

    # Todo: figure out why description isn't always set
    if metadata.get('description'):
        swag["info"]["description"] = metadata.get('description').strip()

    # Fix swagger docs for paths with duplicate operationIds
    # Dict of offending routes (path and method), grouped by operationId
    operations = {}

    for path, path_options in swag['paths'].items():
        for method, route in path_options.items():
            if 'operationId' not in route:
                continue

            operation_id = route['operationId']

            operations.setdefault(operation_id, [])
            operations[operation_id].append({'path': path, 'method': method})

    # Alter route-specific swagger info (using operations dict) to prevent
    # non-unique operationId
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

                if parameter['in'] == 'path' and (
                        "{%s}" % parameter['name']) not in path:
                    # Prevent duplicate operationIds by adding suffix
                    # Assume "simple" version of API route if path parameter
                    # included but not in path
                    swag['paths'][path][method][
                        'operationId'] = "{}-simple".format(operation_id)
                    continue

                parameters.append(parameter)

            # Overwrite old parameter list
            if parameters:
                swag['paths'][path][method]['parameters'] = parameters

            # Add method as suffix to prevent duplicate operationIds on
            # synonymous routes
            if method == 'put' or method == 'post':
                swag['paths'][path][method]['operationId'] = "{}-{}".format(
                    operation_id, method)

    return jsonify(swag)


@portal.route("/celery-test")
def celery_test(x=16, y=16):
    """Simple view to test asynchronous tasks via celery"""
    from ..tasks import add
    x = int(request.args.get("x", x))
    y = int(request.args.get("y", y))
    # Don't queue up a bunch of test tasks; expire if not responsive
    res = add.apply_async((x, y), expires=2.0)
    return jsonify(result=res.get(), task_id=res.task_id)


@portal.route("/celery-info")
def celery_info():
    from ..tasks import info
    res = info.apply_async()
    return jsonify(result=res.get(), task_id=res.task_id)


@portal.route("/task/<task_id>")
@oauth.require_oauth()
def task_result(task_id):
    """Present result from any given (celery) task

    NB actual formatting and permission checks handled by
      ``format_task_output`` - see for details.

    :param task_id: original celery task identifier
    :return: formatted as defined by the job results

    """
    celery = create_celery(current_app)
    task = AsyncResult(task_id, app=celery)
    try:
        retval = task.get(timeout=2)
    except TimeoutError:
        retval = "Operation timed out; task incomplete"
    except Exception as e:
        retval = e

    if isinstance(retval, Exception):
        return jsonify(
            status=task.status, traceback=task.traceback, error=str(retval))
    return format_task_output(retval)


def format_task_output(result):
    """Format background task result

    Present result from a background task as defined within the serialized
    data.

    NB to protect any task result that requires protection include
    ``acting_user_id`` or ``required_roles`` in result dictionary.

    :param result: dictionary defining what and how to present job output,
      as generated by the background task.

    Expected dictionary keys include::
      :lock_key: if defined, release named TimeoutLock
      :required_user_id: if defined, *ONLY* said user can view the result
      :required_roles: if defined (list of role_names), *ONLY* users with
        one of the given role names can view the result
      :response_format: with values such as ``csv`` or ``json``
      :data: actual data to be included

    :return: HTTP Response appropriate for given job result.

    """
    if not isinstance(result, dict):
        # basic task w/o any security or formatting details
        # return simple result representation
        return repr(result)

    def check_permission(user, required_user_id, required_roles):
        """If required_user or required_roles are defined, confirm match

        :raises Unauthorized: if check fails

        """
        if required_user_id and user.id != required_user_id:
            abort(401, "protected task result not available")

        required_role_found = False
        for role_name in required_roles:
            if user.has_role(role_name):
                required_role_found = True
                break
        if required_roles and not required_role_found:
            abort(401, "protected task result not available")

    def release_lock(lock_key):
        """For tasks that use semaphores, release the named lock"""
        if lock_key:
            current_app.logger.debug("Releasing lock '{}'".format(lock_key))
            TimeoutLock(key=lock_key).__exit__(*sys.exc_info())

    response_format = result.get('response_format')
    release_lock(result.get('lock_key'))
    data = result.get('data', [])
    check_permission(
        user=current_user(),
        required_user_id=result.get('required_user_id'),
        required_roles=result.get('required_roles', []))

    if response_format == 'csv':
        def gen(items):
            yield ','.join(column_headers) + '\n'  # header row
            for i in items:
                yield ','.join(
                    ['"{}"'.format(i.get(k, "")) for k in column_headers]
                ) + '\n'

        column_headers = result.get('column_headers', [])
        filename_prefix = result.get('filename_prefix', 'report')
        filename = '{}-{}.csv'.format(
            filename_prefix, strftime('%Y_%m_%d-%H_%M'))

        return Response(gen(data), headers={
            'Content-Disposition': 'attachment;filename={}'.format(filename),
            'Content-type': "text/csv"})

    elif response_format == 'json':
        if hasattr(data, 'get') and data.get(
                'resourceType', None) == 'Bundle':
            return jsonify(data)
        return jsonify(bundle_results(elements=data))
    else:
        abort(400, "unsupported response_format: '{}'".format(
            response_format))


@portal.route("/task/<task_id>/status")
def task_status(task_id):
    """Present known status details for any given celery task

    See also ``task_result`` to obtain task output tailored to original
    request parameters.

    :param task_id: Original task identifier
    :return: formatted details in JSON

    """
    celery = create_celery(current_app)
    task = AsyncResult(task_id, app=celery)
    response = {'state': task.state}
    if getattr(task, 'info') and hasattr(task.info, 'items'):
        response.update(task.info.items())

    # Don't include 'data' if available, as only the result
    # function includes vital security checks
    response.pop('data', None)

    return jsonify(response)


@portal.route('/communicate/preview/<int:comm_id>')
@roles_required([ROLE.ADMIN.value])
@oauth.require_oauth()
def preview_communication(comm_id):
    """Communication message preview"""

    comm = Communication.query.get(comm_id)
    if not comm:
        abort(404, "no communication found for id `{}`".format(comm_id))
    preview = comm.preview()
    return jsonify(subject=preview.subject, body=preview.body,
                   recipients=preview.recipients)


@portal.route("/communicate/<email_or_id>")
@roles_required(ROLE.ADMIN.value)
@oauth.require_oauth()
def communicate(email_or_id):
    """Direct call to trigger communications to given user.

    Typically handled by scheduled jobs, this API enables testing of
    communications without the wait.

    Include a `force=True` query string parameter to first invalidate the cache
    and look for fresh messages before triggering the send.

    Include a `purge=True` query string parameter to throw out existing
    communications for the user first, thus forcing a resend  (implies a force)

    Include a `trace=True` query string parameter to get details found during
    processing - like a debug trace.

    """
    from ..tasks import send_user_messages
    try:
        uid = int(email_or_id)
        u = User.query.get(uid)
    except ValueError:
        u = User.query.filter(User.email == email_or_id).first()
    if not u:
        message = 'no such user'
    elif u.deleted_id:
        message = 'delted user - not allowed'
    else:
        purge = request.args.get('purge', False)
        if purge in ('', '0', 'false', 'False'):
            purge = False
        force = request.args.get('force', purge)
        if force in ('', '0', 'false', 'False'):
            force = False
        trace = request.args.get('trace', False)
        if trace:
            establish_trace("BEGIN trace for communicate on {}".format(u))
        if purge:
            Communication.query.filter_by(user_id=u.id).delete()
        try:
            message = send_user_messages(u, force)
        except ValueError as ve:
            message = "ERROR {}".format(ve)
        if trace:
            message = dump_trace(message)
    return jsonify(message=message)


@portal.route("/post-result/<task_id>")
def post_result(task_id):
    celery = create_celery(current_app)
    r = AsyncResult(task_id, app=celery).get(timeout=1.0)
    return jsonify(status_code=r.status_code, url=r.url, text=r.text)


@portal.route("/legal/stock-org-consent/<org_name>")
def stock_consent(org_name):
    """Simple view to render default consent with named organization

    We generally store the unique URL pointing to the content of the agreement
    to which the user consents.  Special case for organizations without a
    custom consent agreement on file.

    :param org_name: the org_name to include in the agreement text

    """
    body = _("I consent to sharing information with %(org_name)s",
             org_name=_(org_name))
    return render_template_string(
        """<!doctype html>
        <html>
            <head>
            </head>
            <body>
                <p>{{ body }}</p>
            </body>
        </html>""",
        body=body)
