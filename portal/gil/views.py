from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from jinja2 import TemplateNotFound

from ..database import db
from ..extensions import oauth, recaptcha
from ..models.app_text import (
    AboutATMA,
    PrivacyATMA,
    Terms_ATMA,
    VersionedResource,
    app_text,
)
from ..models.coredata import Coredata
from ..models.identifier import Identifier
from ..models.intervention import Intervention
from ..models.message import EmailMessage
from ..models.organization import Organization, OrganizationIdentifier, OrgTree
from ..models.role import ROLE
from ..models.user import current_user, get_user
from ..system_uri import SHORTCUT_ALIAS
from ..views.auth import next_after_login
from ..views.crossdomain import crossdomain

gil = Blueprint(
    'gil', __name__, template_folder='templates', static_folder='static',
    static_url_path='/gil/static')


@gil.errorhandler(404)
def page_not_found(e):
    return render_template(
        'gil/404.html', no_nav="true", user=current_user()), 404


@gil.errorhandler(500)
def server_error(e):  # pragma: no cover
    # NB - this is only hit if app.debug == False
    # exception is automatically sent to log by framework
    return render_template(
        'gil/500.html', no_nav="true", user=current_user()), 500


@gil.route('/')
def landing():
    """landing page view function - present register / login options"""
    if current_user():
        current_app.logger.debug("landing (found user) -> next_after_login")
        return next_after_login()

    timed_out = request.args.get('timed_out', False)
    init_login_modal = False
    if 'pending_authorize_args' in session:
        init_login_modal = True

    return render_template(
        'gil/index.html', user=None, no_nav="true", timed_out=timed_out,
        init_login_modal=init_login_modal)


@gil.route('/home')
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
        return redirect(url_for('gil.landing'))

    # Possible user attempted to avoid flow via browser back
    # and needs to be sent immediately back to appropriate page
    if (not Coredata().initial_obtained(user) or
            'next' in session and session['next']):
        return next_after_login()

    # All checks passed - present appropriate view for user role
    if user.has_role(ROLE.STAFF_ADMIN.value):
        return redirect(url_for('staff.staff_index'))
    if user.has_role(ROLE.STAFF.value, ROLE.INTERVENTION_STAFF.value):
        return redirect(url_for('patients.patients_root'))
    if user.has_role(ROLE.RESEARCHER.value):
        return redirect(url_for('portal.research_dashboard'))

    interventions = Intervention.query.order_by(
        Intervention.display_rank).all()

    consent_agreements = Organization.consent_agreements(
        locale_code=user.locale_code)

    return render_template(
        'gil/portal.html', user=user,
        interventions=interventions, consent_agreements=consent_agreements)


@gil.route('/gil-interventions-items/<int:user_id>')
@crossdomain()
@oauth.require_oauth()
def gil_interventions_items(user_id):
    """ this is needed to filter the GIL menu based on user's intervention(s)
        trying to do this so code is more easily managed from front end side
        Currently it is also accessed via ajax call from gil footer
        see: api/gil-footer-html/
    """
    user = get_user(user_id, permission='view')
    user_interventions = []

    if user:
        interventions = \
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


@gil.route('/gil-shortcut-alias-validation/<string:clinic_alias>')
def gil_shortcut_alias_validation(clinic_alias):
    # Shortcut aliases are registered with the organization as identifiers.
    # Confirm the requested alias exists or 404
    identifier = Identifier.query.filter_by(system=SHORTCUT_ALIAS,
                                            _value=clinic_alias).first()
    if not identifier:
        current_app.logger.debug("Clinic alias not found: %s", clinic_alias)
        return jsonify({"error": "clinic alias not found"})

    # Expecting exactly one organization for this alias, return if found
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
                return jsonify(
                    {"error": "alias points to top-level organization"})

    identifier = {"name": org.name}
    return jsonify(identifier)


@gil.route('/privacy')
def privacy():
    """ privacy use page"""
    user = current_user()
    locale_code = user.locale_code if user else None
    privacy_resource = VersionedResource(
        app_text(PrivacyATMA.name_key()), locale_code=locale_code)
    return render_template(
        'gil/privacy.html', content=privacy_resource.asset, user=user,
        editorUrl=privacy_resource.editor_url)


@gil.route('/terms')
def terms_and_conditions():
    """ terms-and-conditions of use page"""
    user = current_user()
    if user:
        role = None
        if user.has_role(ROLE.STAFF.value, ROLE.STAFF_ADMIN.value):
            role = ROLE.STAFF.value
        elif user.has_role(ROLE.PATIENT.value):
            role = ROLE.PATIENT.value
        terms = VersionedResource(
            app_text(Terms_ATMA.name_key(role=role)),
            locale_code=user.locale_code)
    else:
        terms = VersionedResource(
            app_text(Terms_ATMA.name_key()), locale_code=None)
    return render_template('gil/terms.html', content=terms.asset,
                           editorUrl=terms.editor_url, user=user)


@gil.route('/about')
def about():
    """main TrueNTH about page"""
    user = current_user()
    locale_code = user.locale_code if user else None
    about_tnth = VersionedResource(
        app_text(AboutATMA.name_key(subject='TrueNTH')),
        locale_code=locale_code)
    return render_template(
        'gil/about.html',
        about_tnth=about_tnth.asset,
        about_tnth_editorUrl=about_tnth.editor_url,
        user=user)


@gil.route('/contact', methods=('GET', 'POST'))
def contact():
    """main TrueNTH contact page"""
    user = current_user()
    if request.method == 'GET':
        sendername = user.display_name if user else ''
        email = user.email if user else ''
        recipient_types = []
        for org in Organization.query.filter(Organization.email.isnot(None)):
            if '@' in org.email:
                recipient_types.append((org.name, org.email))
        return render_template(
            'gil/contact.html', sendername=sendername, email=email, user=user,
            types=recipient_types)

    if (not user and
            current_app.config.get('RECAPTCHA_SITE_KEY', None) and
            current_app.config.get('RECAPTCHA_SECRET_KEY', None) and
            not recaptcha.verify()):
        abort(400, "Recaptcha verification failed")
    sender = request.form.get('email')
    if not sender or ('@' not in sender):
        abort(400, "No valid sender email address provided")
    sendername = request.form.get('sendername')
    subject = "{server} contact request: {subject}".format(
        server=current_app.config['SERVER_NAME'],
        subject=request.form.get('subject'))
    if len(sendername) > 255:
        abort(400, "Sender name max character length exceeded")
    if len(subject) > 255:
        abort(400, "Subject max character length exceeded")
    formbody = request.form.get('body')
    if not formbody:
        abort(400, "No contact request body provided")
    body = "From: {sendername}<br />Email: {sender}<br /><br />{body}".format(
        sendername=sendername, sender=sender, body=formbody)
    recipient = request.form.get('type')
    recipient = recipient or current_app.config['CONTACT_SENDTO_EMAIL']
    if not recipient:
        abort(400, "No recipient found")

    user_id = user.id if user else None
    email = EmailMessage(subject=subject, body=body, recipients=recipient,
                         sender=sender, user_id=user_id)
    email.send_message()
    db.session.add(email)
    db.session.commit()
    return jsonify(msgid=email.id)


@gil.route('/symptom-tracker')
def symptom_tracker():
    return render_template('gil/symptom-tracker.html', user=current_user())


@gil.route('/decision-support')
def decision_support():
    return render_template('gil/decision-support.html', user=current_user())


@gil.route('/what-is-prostate-cancer')
def prostate_cancer_facts():
    return render_template(
        'gil/what-is-prostate-cancer.html', user=current_user())


@gil.route('/exercise-and-diet')
def exercise_and_diet():
    return redirect(url_for('exercise_diet.introduction'))


@gil.route('/lived-experience')
def lived_experience():
    return render_template('gil/lived-experience.html', user=current_user())


@gil.route('/sexual-wellbeing')
def sexual_wellbeing():
    return render_template(
        'gil/sexual_wellbeing.html', user=current_user())

@gil.route('/stories/<string:page_name>')
def stories(page_name):
    try:
        return render_template('gil/%s.html' % page_name.replace('-', '_'))
    except TemplateNotFound as err:
        abort(404)
