"""Portal view functions (i.e. not part of the API or auth)"""
from collections import defaultdict
from flask import current_app, Blueprint, jsonify, render_template, flash
from flask import abort, make_response, redirect, request, session, url_for
from flask import render_template_string
from flask_babel import gettext as _
from flask_user import roles_required
from flask_swagger import swagger
from flask_wtf import FlaskForm
from pprint import pformat
from sqlalchemy import and_
from sqlalchemy.orm.exc import NoResultFound
from wtforms import validators, HiddenField, IntegerField, StringField
from datetime import datetime

from .auth import next_after_login, logout
from ..audit import auditable_event
from .crossdomain import crossdomain
from ..database import db
from ..extensions import oauth, recaptcha, user_manager
from ..models.app_text import app_text, AppText, VersionedResource, UndefinedAppText
from ..models.app_text import (AboutATMA, InitialConsent_ATMA, PrivacyATMA,
                               StaffRegistrationEmail_ATMA)
from ..models.app_text import Terms_ATMA, WebsiteConsentTermsByOrg_ATMA, WebsiteDeclarationForm_ATMA
from ..models.auth import validate_client_origin, validate_local_origin
from ..models.coredata import Coredata
from ..models.fhir import CC
from ..models.i18n import get_locale
from ..models.identifier import Identifier
from ..models.intervention import Intervention
from ..models.message import EmailMessage
from ..models.organization import Organization, OrganizationIdentifier, OrgTree, UserOrganization
from ..models.procedure_codes import known_treatment_started
from ..models.procedure_codes import known_treatment_not_started
from ..models.role import Role, ROLE, ALL_BUT_WRITE_ONLY
from ..models.user import current_user, get_user, User, UserRoles
from ..system_uri import SHORTCUT_ALIAS
from ..tasks import add, info, post_request
from jinja2 import TemplateNotFound


portal = Blueprint('portal', __name__)


def page_not_found(e):
    gil = current_app.config.get('GIL')
    return render_template('404.html' if not gil else '/gil/404.html', no_nav="true", user=current_user()), 404


def server_error(e):  # pragma: no cover
    # NB - this is only hit if app.debug == False
    # exception is automatically sent to log by framework
    gil = current_app.config.get('GIL')
    return render_template('500.html' if not gil else '/gil/500.html', no_nav="true", user=current_user()), 500


@portal.before_app_request
def assert_locale_selector():
    # Confirm import & use of custom babel localeselector function.
    # Necessary to import get_locale to bring into the request scope to
    # prevent the default babel locale selector from being used.
    assert get_locale()


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


@portal.route('/')
def landing():
    """landing page view function - present register / login options"""
    if current_user():
        current_app.logger.debug("landing (found user) -> next_after_login")
        return next_after_login()

    timed_out = request.args.get('timed_out', False)
    gil = current_app.config.get('GIL')
    init_login_modal = False
    if 'pending_authorize_args' in session:
        init_login_modal = True
    return render_template('landing.html' if not gil else 'gil/index.html', user=None, no_nav="true", timed_out=timed_out, init_login_modal=init_login_modal)

#from GIL
@portal.route('/gil-interventions-items/<int:user_id>')
@crossdomain()
def gil_interventions_items(user_id):
    """ this is needed to filter the GIL menu based on user's intervention(s)
        trying to do this so code is more easily managed from front end side
        Currently it is also accessed via ajax call from portal footer
        see: api/portal-footer-html/
    """
    user = None

    if user_id:
        user = get_user(user_id)
    else:
        user = current_user()

    user_interventions = []

    if user:
        interventions =\
                Intervention.query.order_by(Intervention.display_rank).all()
        for intervention in interventions:
            display = intervention.display_for_user(user)
            if display.access:
                user_interventions.append({
                    "name": intervention.name,
                    "description": intervention.description if intervention.description else "",
                    "link_url": display.link_url if display.link_url is not None else "disabled",
                    "link_label": display.link_label if display.link_label is not None else ""
                })

    return jsonify(interventions=user_interventions)

@portal.route('/gil-shortcut-alias-validation/<string:clinic_alias>')
def gil_shortcut_alias_validation(clinic_alias):
    # Shortcut aliases are registered with the organization as identifiers.
    # Confirm the requested alias exists or 404
    identifier = Identifier.query.filter_by(system=SHORTCUT_ALIAS,
                                            _value=clinic_alias).first()
    if not identifier:
        current_app.logger.debug("Clinic alias not found: %s", clinic_alias)
        return jsonify({"error": "clinic alias not found"})

    # Expecting exactly one organization for this alias, save ID in session
    results = OrganizationIdentifier.query.filter_by(
        identifier_id=identifier.id).one()
    # Top-level orgs with child orgs won't work, as the UI only lists the clinic level
    org = Organization.query.get(results.organization_id)
    if org.partOf_id is None:
        OT = OrgTree()
        orgs = OT.here_and_below_id(results.organization_id)
        for childOrg in orgs:
            # the org tree contains an org other than the alias org itself
            if childOrg != results.organization_id:
                return jsonify({"error": "alias points to top-level organization"})

    identifier = {"name": org.name}


    return jsonify(identifier)

@portal.route('/symptom-tracker')
def symptom_tracker():
    return render_template('gil/symptom-tracker.html', user=current_user())

@portal.route('/decision-support')
def decision_support():
    return render_template('gil/decision-support.html', user=current_user())

@portal.route('/what-is-prostate-cancer')
def prostate_cancer_facts():
    return render_template('gil/what-is-prostate-cancer.html', user=current_user())

@portal.route('/exercise-and-diet')
def exercise_and_diet():
    return render_template('gil/exercise-and-diet.html', user=current_user())

@portal.route('/lived-experience')
def lived_experience():
    return render_template('gil/lived-experience.html', user=current_user())

@portal.route('/stories/<string:page_name>')
def stories(page_name):
    try:
        return render_template('gil/%s.html' % page_name.replace('-', '_'))
    except TemplateNotFound as err:
        return page_not_found(err)

class ShortcutAliasForm(FlaskForm):
    shortcut_alias = StringField('Code', validators=[validators.Required()])

    def validate_shortcut_alias(form, field):
        """Custom validation to confirm an alias match"""
        if len(field.data.strip()):
            try:
                Identifier.query.filter_by(
                    system=SHORTCUT_ALIAS, _value=field.data).one()
            except NoResultFound:
                raise validators.ValidationError("Code not found")


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
        return redirect(url_for('portal.home'))

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

    # Top-level orgs with child orgs won't work, as the UI only lists the clinic level
    org = Organization.query.get(results.organization_id)
    if org.partOf_id is None:
        OT = OrgTree()
        orgs = OT.here_and_below_id(results.organization_id)
        for childOrg in orgs:
            # the org tree contains an org other than the alias org itself
            if childOrg != results.organization_id:
                abort(400, "alias points to top-level organization")

    session['associate_clinic_id'] = results.organization_id
    current_app.logger.debug(
        "Storing session['associate_clinic_id']{}".format(
            session['associate_clinic_id']))

    return redirect(url_for('user.register'))


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
    # logout current user if one is logged in.
    if current_user():
        logout(prevent_redirect=True, reason="forced from /access_via_token")
        assert(not current_user())

    def verify_token(valid_seconds):
        is_valid, has_expired, user_id =\
                user_manager.token_manager.verify_token(token, valid_seconds)
        if has_expired:
            flash('Your access token has expired.', 'error')
            return redirect(url_for('portal.landing'))
        if not is_valid:
            flash('Your access token is invalid.', 'error')
            return redirect(url_for('portal.landing'))
        return user_id

    # Confirm the token is valid, and not expired.
    valid_seconds = current_app.config.get(
        'TOKEN_LIFE_IN_DAYS', 30) * 24 * 3600
    user_id = verify_token(valid_seconds)

    # Valid token - confirm user id looks legit
    user = get_user(user_id)
    if user.deleted:
        abort(400, "deleted user - operation not permitted")
    not_allowed = set([ROLE.ADMIN, ROLE.APPLICATION_DEVELOPER, ROLE.SERVICE])
    has = set([role.name for role in user.roles])
    if not has.isdisjoint(not_allowed):
        abort(400, "Access URL not allowed for privileged accounts")
    if ROLE.WRITE_ONLY in has:
        # write only users with special role skip the challenge protocol
        if ROLE.PROMOTE_WITHOUT_IDENTITY_CHALLENGE in has:
            # only give such tokens 5 minutes - recheck validity
            verify_token(valid_seconds=5*60)
            auditable_event("promoting user without challenge via token, "
                            "pending registration", user_id=user.id,
                            subject_id=user.id, context='account')
            user.mask_email()
            db.session.commit()
            session['invited_verified_user_id'] = user.id
            return redirect(url_for('user.register', email=user.email))

        # If WRITE_ONLY user does not have PROMOTE_WITHOUT_IDENTITY_CHALLENGE,
        # challenge the user identity, followed by a redirect to the
        # registration page. Preserve the invited user id, should we need to
        # merge associated details after user proves themselves and logs in
        auditable_event("invited user entered using token, pending "
                        "registration", user_id=user.id, subject_id=user.id,
                        context='account')
        session['challenge.user_id'] = user.id
        session['challenge.next_url'] = url_for('user.register', email=user.email)
        session['challenge.merging_accounts'] = True
        return redirect(url_for('portal.challenge_identity'))

    # If not WRITE_ONLY user, redirect to login page
    # Email field is auto-populated unless using alt auth (fb/google/etc)
    if user.email and user.password:
        return redirect(url_for('user.login', email=user.email))
    return redirect(url_for('user.login'))


class ChallengeIdForm(FlaskForm):
    retry_count = HiddenField('retry count', default=0)
    next_url = HiddenField('next')
    user_id = HiddenField('user')
    merging_accounts = HiddenField('merging_accounts')
    first_name = StringField(
        'First Name', validators=[validators.input_required()])
    last_name = StringField(
        'Last Name', validators=[validators.input_required()])
    birthdate = StringField(
        'Birthdate', validators=[validators.input_required()])


@portal.route('/challenge', methods=['GET', 'POST'])
def challenge_identity(user_id=None, next_url=None, merging_accounts=False):
    """Challenge the user to verify themselves

    Can't expose the parameters for security reasons - use the session,
    namespace each variable i.e. session['challenge.user_id'] unless
    calling as a function.

    :param user_id: the user_id to verify - invited user or the like
    :param next_url: destination url on successful challenge completion
    :param merging_accounts: boolean value, set true IFF on success, the
        user account will be merged into a new account, say from a weak
        authenicated WRITE_ONLY invite account

    """
    if request.method == 'GET':
        # Pull parameters from session if not defined
        if not (user_id and next_url):
            user_id = session.get('challenge.user_id')
            next_url = session.get('challenge.next_url')
            merging_accounts = session.get('challenge.merging_accounts', False)

    if request.method == 'POST':
        form = ChallengeIdForm(request.form)
        if form.next_url.data:
            validate_local_origin(form.next_url.data)
        if not form.user_id.data:
            abort(400, "missing user in identity challenge")
        user = get_user(form.user_id.data)
        if not user:
            abort(400, "missing user in identity challenge")
    else:
        user = get_user(user_id)
        if not user:
            abort(400, "missing user in identity challenge")
        form = ChallengeIdForm(
            next_url=next_url, user_id=user.id,
            merging_accounts=merging_accounts)

    errorMessage = ""
    if not form.validate_on_submit():
        return render_template(
            'challenge_identity.html', form=form, errorMessage=errorMessage)

    first_name = form.first_name.data
    last_name = form.last_name.data
    birthdate = datetime.strptime(form.birthdate.data, '%m-%d-%Y');

    score = user.fuzzy_match(first_name=first_name,
                             last_name=last_name,
                             birthdate=birthdate)
    if score > current_app.config.get('IDENTITY_CHALLENGE_THRESHOLD', 85):
        # identity confirmed
        session['challenge_verified_user_id'] = user.id
        if form.merging_accounts.data == 'True':
            user.mask_email()
            db.session.commit()
            session['invited_verified_user_id'] = user.id
        return redirect(form.next_url.data)

    else:
        auditable_event("Failed identity challenge tests with values:"
                        "(first_name={}, last_name={}, birthdate={})".\
                        format(first_name, last_name, birthdate),
                        user_id=user.id, subject_id=user.id,
                        context='authentication')
        # very modest brute force test
        form.retry_count.data = int(form.retry_count.data) + 1
        if form.retry_count.data >= 1:
            errorMessage = "Unable to match identity"
        if form.retry_count.data > 3:
            abort(404, "User Not Found")

        return render_template(
            'challenge_identity.html', form=form, errorMessage=errorMessage)


@portal.route('/initial-queries', methods=['GET','POST'])
def initial_queries():
    """Initial consent terms, initial queries view function"""
    if request.method == 'POST':
        # data submission all handled via ajax calls from initial_queries
        # template.  assume POST can only be sent when valid.
        current_app.logger.debug("POST initial_queries -> next_after_login")
        return next_after_login()

    user = current_user()
    if not user:
        # Shouldn't happen, unless user came in on a bookmark
        current_app.logger.debug("initial_queries (no user!) -> landing")
        return redirect(url_for('portal.landing'))
    if user.deleted:
        abort(400, "deleted user - operation not permitted")

    still_needed = Coredata().still_needed(user)
    terms, consent_agreements = None, {}
    org = user.first_top_organization()
    role = None
    if not current_app.config.get('GIL'):
        for r in (ROLE.STAFF_ADMIN, ROLE.STAFF, ROLE.PATIENT):
            if user.has_role(r):
                # treat staff_admins as staff for this lookup
                r = ROLE.STAFF if r == ROLE.STAFF_ADMIN else r
                role = r
    terms = get_terms(org, role)
    #need this at all time now for ui
    consent_agreements = Organization.consent_agreements()
    return render_template(
        'initial_queries.html', user=user, terms=terms,
        consent_agreements=consent_agreements, still_needed=still_needed)


@portal.route('/website-consent-script/<int:patient_id>', methods=['GET'])
@roles_required(ROLE.STAFF)
@oauth.require_oauth()
def website_consent_script(patient_id):
    entry_method = request.args.get('entry_method', None)
    redirect_url = request.args.get('redirect_url', None)
    if redirect_url:
        """
        redirect url here is the patient's assessment link
        /api/present-assessment, so validate against local origin
        """
        validate_local_origin(redirect_url)
    user = current_user()
    patient = get_user(patient_id)
    org = patient.first_top_organization()
    """
    NOTE, we are getting PATIENT's website consent terms here
    as STAFF member needs to read the terms to the patient
    """
    terms = get_terms(org, ROLE.PATIENT)
    top_org = patient.first_top_organization()
    declaration_form = VersionedResource(app_text(WebsiteDeclarationForm_ATMA.
                                                  name_key(organization=top_org)))
    return render_template(
        'website_consent_script.html', user=user,
        terms=terms, top_organization=top_org,
        entry_method=entry_method, redirect_url=redirect_url,
        declaration_form=declaration_form, patient_id=patient_id)


def get_terms(org=None, role=None):
    terms = None

    if org:
        try:
            terms = VersionedResource(app_text(WebsiteConsentTermsByOrg_ATMA.
                                               name_key(organization=org, role=role)))
        except UndefinedAppText:
            terms = VersionedResource(app_text(InitialConsent_ATMA.name_key()))

    else:
        terms = VersionedResource(app_text(InitialConsent_ATMA.name_key()))

    return terms

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
        return redirect(url_for('portal.landing'))

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
    if user.has_role(ROLE.STAFF) or user.has_role(ROLE.INTERVENTION_STAFF):
        return redirect(url_for('patients.patients_root'))

    interventions =\
            Intervention.query.order_by(Intervention.display_rank).all()

    gil = current_app.config.get('GIL')
    consent_agreements = {}
    if gil:
        consent_agreements = Organization.consent_agreements()

    return render_template(
        'portal.html' if not gil else 'gil/portal.html', user=user,
        interventions=interventions, consent_agreements=consent_agreements)


@portal.route('/admin')
@roles_required(ROLE.ADMIN)
@oauth.require_oauth()
def admin():
    """user admin view function"""
    # can't do list comprehension in template - prepopulate a 'rolelist'
    users = User.query.filter_by(deleted=None).all()
    for u in users:
        u.rolelist = ', '.join([r.name for r in u.roles])
    return render_template('admin.html', users=users, wide_container="true", user=current_user())


@portal.route('/staff-profile-create')
@roles_required(ROLE.STAFF_ADMIN)
@oauth.require_oauth()
def staff_profile_create():
    consent_agreements = Organization.consent_agreements()
    user = current_user()

    #compiling org list for staff
    #org list should include all orgs under the current user's org(s)
    OT = OrgTree()
    org_list = set()
    for org in user.organizations:
        if org.id == 0:  # None of the above doesn't count
            continue
        org_list.update(OT.here_and_below_id(org.id))

    return render_template(
        "staff_profile_create.html", user=user,
        consent_agreements=consent_agreements,
        org_list=list(org_list))

@portal.route('/staff')
@roles_required(ROLE.STAFF_ADMIN)
@oauth.require_oauth()
def staff():
    """staff view function, intended for staff admin

    Present the logged in staff admin the list of staff matching
    the staff admin's organizations (and any decendent organizations)

    """
    user = current_user()

    OT = OrgTree()

    staff_role_id = Role.query.filter(
        Role.name==ROLE.STAFF).with_entities(Role.id).first()
    admin_role_id = Role.query.filter(
        Role.name==ROLE.ADMIN).with_entities(Role.id).first()
    staff_admin_role_id = Role.query.filter(
        Role.name==ROLE.STAFF_ADMIN).with_entities(Role.id).first()

    # empty patient query list to start, unionize with other relevant lists
    staff_list = User.query.filter(User.id==-1)

    org_list = set()

    user_orgs = set()

    # Build list of all organization ids, and their decendents, the
    # user belongs to
    for org in user.organizations:
        if org.id == 0:  # None of the above doesn't count
            continue
        org_list.update(OT.here_and_below_id(org.id))
        user_orgs.add(org.id)

    #Gather up all staff admin and admin that belongs to user's org(s)
    admin_staff = User.query.join(UserRoles).filter(
        and_(User.id==UserRoles.user_id,
             UserRoles.role_id.in_([admin_role_id, staff_admin_role_id]),
             User.deleted_id==None
             )
        ).join(UserOrganization).filter(
            and_(UserOrganization.user_id==User.id,
                 UserOrganization.organization_id.in_(user_orgs)))
    admin_list = [u.id for u in admin_staff]


    # Gather up all staff belonging to any of the orgs (and their children)
    # NOTE, need to exclude staff_admin or admin user at the same org(s) as the user
    # as the user should NOT be able to edit their record
    org_staff = User.query.join(UserRoles).filter(
        and_(User.id==UserRoles.user_id,
            ~User.id.in_(admin_list),
             UserRoles.role_id==staff_role_id,
             User.deleted_id==None
             )
        ).join(UserOrganization).filter(
            and_(UserOrganization.user_id==User.id,
                 UserOrganization.organization_id.in_(org_list)))
    staff_list = staff_list.union(org_staff)

    return render_template(
        'staff_by_org.html', staff_list=staff_list.all(),
        user=user, wide_container="true")


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
    if not user.email:
        abort(400, "Users without an email address can't send email")
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
@roles_required(ALL_BUT_WRITE_ONLY)
@oauth.require_oauth()
def profile(user_id):
    """profile view function"""
    user = current_user()
    if user_id:
        user.check_role("edit", other_id=user_id)
        user = get_user(user_id)
    consent_agreements = Organization.consent_agreements()
    terms = VersionedResource(app_text(InitialConsent_ATMA.name_key()))
    return render_template(
        'profile.html', user=user, consent_agreements=consent_agreements, terms=terms)

@portal.route('/privacy')
def privacy():
    """ privacy use page"""
    gil = current_app.config.get('GIL')
    user = current_user()
    if gil:
        privacy_resource = VersionedResource(app_text(PrivacyATMA.name_key()))
    elif user:
        organization = user.first_top_organization()
        role = None
        for r in (ROLE.STAFF, ROLE.PATIENT):
            if user.has_role(r):
                role = r
        # only include role and organization if both are defined
        if not all((role, organization)):
            role, organization = None, None

        privacy_resource = VersionedResource(app_text(
            PrivacyATMA.name_key(role=role, organization=organization)))
    else:
        abort(400, "No publicly viewable privacy policy page available")

    return render_template(
        'privacy.html' if not gil else 'gil/privacy.html',
        content=privacy_resource.asset, user=user,
        editorUrl=privacy_resource.editor_url)

@portal.route('/terms')
def terms_and_conditions():
    """ terms-and-conditions of use page"""
    gil = current_app.config.get('GIL')
    user = current_user()
    if user and not gil:
        organization = user.first_top_organization()
        role = None
        for r in (ROLE.STAFF, ROLE.PATIENT):
            if user.has_role(r):
                role = r
        # only include role and organization if both are defined
        if not all((role, organization)):
            role, organization = None, None

        terms = VersionedResource(app_text(Terms_ATMA.name_key(
            role=role, organization=organization)))
    else:
        terms = VersionedResource(app_text(Terms_ATMA.name_key()))

    return render_template('terms.html' if not gil else 'gil/terms.html',
        content=terms.asset, editorUrl=terms.editor_url, user=user)

@portal.route('/about')
def about():
    """main TrueNTH about page"""
    about_tnth = VersionedResource(
        app_text(AboutATMA.name_key(subject='TrueNTH')))
    about_mo = VersionedResource(
        app_text(AboutATMA.name_key(subject='Movember')))
    gil = current_app.config.get('GIL')
    return render_template(
        'about.html' if not gil else 'gil/about.html',
        about_tnth=about_tnth.asset,
        about_mo=about_mo.asset,
        about_tnth_editorUrl=about_tnth.editor_url,
        about_mo_editorUrl=about_mo.editor_url,
        user=current_user())


@roles_required([ROLE.ADMIN, ROLE.STAFF_ADMIN])
@oauth.require_oauth()
@portal.route('/staff-registration-email/<int:user_id>')
def staff_registration_email(user_id):
    """Staff Registration Email Content"""
    if user_id:
        user = get_user(user_id)
    else:
        user = current_user()

    org = user.first_top_organization()

    try:
        item = VersionedResource(app_text(StaffRegistrationEmail_ATMA.
                                          name_key(organization=org)))
    except UndefinedAppText:
        """return no content and 204 no content status"""
        return ('', 204)

    return make_response(item.asset)

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

@portal.route('/robots.txt')
def robots():
    if current_app.config["SYSTEM_TYPE"].lower() == "production":
        return "User-agent: * \nAllow: /"
    return "User-agent: * \nDisallow: /"

@portal.route('/contact', methods=('GET', 'POST'))
def contact():
    """main TrueNTH contact page"""
    user = current_user()
    if request.method == 'GET':
        sendername = user.display_name if user else ''
        email = user.email if user else ''
        gil = current_app.config.get('GIL')
        return render_template('contact.html' if not gil else 'gil/contact.html', sendername=sendername,
                               email=email, user=user)

    if (not user and
            current_app.config.get('RECAPTCHA_SITE_KEY', None) and
            current_app.config.get('RECAPTCHA_SECRET_KEY', None) and
            not recaptcha.verify()):
        abort(400, "Recaptcha verification failed")
    sender = request.form.get('email')
    if not sender or ('@' not in sender):
        abort(400, "No valid sender email address provided")
    sendername = request.form.get('sendername')
    subject = u"{server} contact request: {subject}".format(
        server=current_app.config['SERVER_NAME'],
        subject=request.form.get('subject'))
    if len(sendername) > 255:
        abort(400, "Sender name max character length exceeded")
    if len(subject) > 255:
        abort(400, "Subject max character length exceeded")
    formbody = request.form.get('body')
    if not formbody:
        abort(400, "No contact request body provided")
    body = u"From: {sendername}<br />Email: {sender}<br /><br />{body}".format(
        sendername=sendername, sender=sender, body=formbody)
    recipients = current_app.config['CONTACT_SENDTO_EMAIL']

    user_id = user.id if user else None
    email = EmailMessage(subject=subject, body=body,
            recipients=recipients, sender=sender, user_id=user_id)
    email.send_message()
    db.session.add(email)
    db.session.commit()
    return jsonify(msgid=email.id)

@portal.route('/contact/<int:message_id>')
def contact_sent(message_id):
    """show invite sent"""
    message = EmailMessage.query.get(message_id)
    if not message:
        abort(404, "Message not found")
    return render_template('contact_sent.html', message=message)


class SettingsForm(FlaskForm):
    timeout = IntegerField('Session Timeout for This Web Browser (in seconds)',
                           validators=[validators.Required()])


@portal.route('/settings', methods=['GET', 'POST'])
@roles_required(ROLE.ADMIN)
@oauth.require_oauth()
def settings():
    """settings panel for admins"""
    # load all top level orgs and consent agreements
    organization_consents = Organization.consent_agreements()

    # load all app text values - expand when possible
    apptext = {}
    for a in AppText.query.all():
        try:
            # expand strings with just config values, such as LR
            apptext[a.name] = app_text(a.name)
        except ValueError:
            # lack context to expand, show with format strings
            apptext[a.name] = a.custom_text

    form = SettingsForm(
        request.form, timeout=request.cookies.get('SS_TIMEOUT', 600))
    if not form.validate_on_submit():

        return render_template(
            'settings.html',
            form=form,
            apptext=apptext,
            organization_consents=organization_consents,
            wide_container="true")

    # make max_age outlast the browser session
    max_age = 60 * 60 * 24 * 365 * 5
    response = make_response(render_template(
        'settings.html',
        form=form,
        apptext=apptext,
        organization_consents=organization_consents,
        wide_container="true"))
    response.set_cookie('SS_TIMEOUT', str(form.timeout.data), max_age=max_age)
    return response


@portal.route('/api/settings/<string:config_key>')
@oauth.require_oauth()
def config_settings(config_key):
    key = config_key.upper()
    available = ['LR_ORIGIN', 'LR_GROUP']
    if key in available:
        return jsonify({key: current_app.config.get(key)})
    else:
        abort(400, "Configuration key '{}' not available".format(key))


@portal.route('/reporting')
@roles_required([ROLE.ADMIN, ROLE.ANALYST])
@oauth.require_oauth()
def reporting_dashboard():
    """Executive Reporting Dashboard

    Only accessible to Admins, or those with the Analyst role (no PHI access).

    Usage: graphs showing user registrations and logins per day;
           filterable by date and/or by intervention

    User Stats: counts of users by role, intervention, etc.

    Institution Stats: counts of users per org

    Analytics: Usage stats from piwik (time on site, geographic usage,
               referral sources for new visitors, etc)

    """
    counts = {}
    counts['roles'] = defaultdict(int)
    counts['patients'] = defaultdict(int)
    counts['interventions'] = defaultdict(int)
    counts['intervention_reports'] = defaultdict(int)
    counts['organizations'] = defaultdict(int)

    for user in User.query.filter_by(active=True):
        for role in user.roles:
            counts['roles'][role.name] += 1
            if role.name == 'patient':
                if not any((obs.codeable_concept == CC.BIOPSY
                            and obs.value_quantity.value)
                           for obs in user.observations):
                    counts['patients']['pre-dx'] += 1
                elif known_treatment_not_started(user):
                    counts['patients']['dx-nt'] += 1
                elif known_treatment_started(user):
                    counts['patients']['dx-t'] += 1
                if any((obs.codeable_concept == CC.PCaLocalized
                        and not obs.value_quantity.value)
                       for obs in user.observations):
                    counts['patients']['meta'] += 1
        for interv in user.interventions:
            counts['interventions'][interv.description] += 1
            if (any(doc.intervention == interv for doc in user.documents)):
                counts['intervention_reports'][interv.description] += 1
        for org in user.organizations:
            counts['organizations'][org.name] += 1

    return render_template('reporting_dashboard.html', counts=counts)


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


@portal.route("/celery-info")
def celery_info():
    res = info.apply_async(())
    context = {"id": res.task_id}
    task_id = "{}".format(context['id'])
    result_url = url_for('.celery_result', task_id=task_id)
    if request.args.get('redirect-to-result', None):
        return redirect(result_url)
    return jsonify(task_id=task_id, result_url=result_url)


@portal.route("/celery-result/<task_id>")
def celery_result(task_id):
    retval = add.AsyncResult(task_id).get(timeout=1.0)
    return repr(retval)


@portal.route("/post-result/<task_id>")
def post_result(task_id):
    r = post_request.AsyncResult(task_id).get(timeout=1.0)
    return jsonify(status_code=r.status_code, url=r.url, text=r.text)

@portal.route("/legal/stock-org-consent/<org_name>")
def stock_consent(org_name):
    """Simple view to render default consent with named organization

    We generally store the unique URL pointing to the content of the agreement
    to which the user consents.  Special case for organizations without a
    custom consent agreement on file.

    :param org_name: the org_name to include in the agreement text

    """
    return render_template_string(
        """<!doctype html>
        <html>
            <head>
            </head>
            <body>
                <p>I consent to sharing information with the {{ org_name }}</p>
            </body>
        </html>""",
        org_name=org_name)


def check_int(i):
    try:
        return int(i)
    except ValueError, e:
        abort(400, "invalid input '{}' - must be an integer".format(i))
