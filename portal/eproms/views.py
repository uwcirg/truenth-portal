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
from flask_user import roles_required

from ..database import db
from ..date_tools import localize_datetime
from ..extensions import oauth, recaptcha
from ..models.app_text import (
    AboutATMA,
    PrivacyATMA,
    Terms_ATMA,
    VersionedResource,
    WebsiteDeclarationForm_ATMA,
    app_text,
    get_terms,
)
from ..models.client import validate_origin
from ..models.coredata import Coredata
from ..models.intervention import Intervention
from ..models.message import EmailMessage
from ..models.organization import Organization
from ..models.role import ROLE
from ..models.user import current_user, get_user
from ..views.auth import next_after_login
from ..views.external_assets import (
    asset_by_uuid,
    get_all_tag_data,
    get_any_tag_data,
)

eproms = Blueprint(
    'eproms', __name__, template_folder='templates', static_folder='static',
    static_url_path='/eproms/static')


@eproms.errorhandler(404)
def page_not_found(e):
    return render_template(
        'eproms/404.html', no_nav="true", user=current_user()), 404


@eproms.errorhandler(500)
def server_error(e):  # pragma: no cover
    # NB - this is only hit if app.debug == False
    # exception is automatically sent to log by framework
    return render_template(
        'eproms/500.html', no_nav="true", user=current_user()), 500


@eproms.route('/')
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
        'eproms/landing.html', user=None, no_nav="true",
        timed_out=timed_out,
        init_login_modal=init_login_modal)


def assessment_engine_view(user):
    """View like function for this very special intervention

    Most interventions maintain a small block of HTML in the interventions
    or (when customized per user) in the user_interventions table.

    The assessment engine is special, as much of the state used to determine
    logic switches within the displayed HTML only lives within the portal
    and not with the intervention.  Furthermore, the displayed HTML exceeds
    the "card" model, is significantly more complex (i.e. modal use) and
    therefore gets this function to render the "main well" of the page used
    to display intervention cards.

    NB - not a real flask view method, as the returned HTML needs to be
    embedded within another page, not made into a response object.

    """
    from datetime import datetime
    from ..models.overall_status import OverallStatus
    from ..models.qb_status import QB_Status  # avoid cycle
    now = datetime.utcnow()

    # TODO handle research study id.  Patient must be done with study 0
    #  before seeing any study 1 work.
    research_study_id = 0
    assessment_status = QB_Status(
        user=user,
        research_study_id=research_study_id,
        as_of_date=now)
    current_app.logger.debug("{}".format(assessment_status))
    indefinite_questionnaires = (
        assessment_status.instruments_needing_full_assessment(
            classification='indefinite'),
        assessment_status.instruments_in_progress(
            classification='indefinite'))
    # variables needed for the templates
    due_date = localize_datetime(
        assessment_status.due_date, user) \
        if assessment_status.due_date else None
    expired_date = localize_datetime(assessment_status.expired_date, user) \
        if assessment_status.expired_date else None
    comp_date = localize_datetime(assessment_status.completed_date, user) \
        if assessment_status.completed_date else None
    assessment_is_due = (
        assessment_status.overall_status == OverallStatus.overdue) \
        or (assessment_status.due_date is not None
            and assessment_status.due_date < now)

    # TODO resolve what portions of this logic could better be handled
    #  within the templates

    # From thank you block:
    thankyou_block = render_template(
        "eproms/assessment_engine/ae_thankyou.html",
        assessment_status=assessment_status,
        OverallStatus=OverallStatus,
        full_name=user.display_name,
        registry=assessment_status.assigning_authority)
    due_block = render_template(
        "eproms/assessment_engine/ae_due.html",
        assessment_status=assessment_status,
        OverallStatus=OverallStatus,
        full_name=user.display_name,
        due_date=due_date,
        expired_date=expired_date,
        assessment_is_due=assessment_is_due,
        comp_date=comp_date)
    indefinite_due_block = render_template(
        "eproms/assessment_engine/ae_indefinite_due.html",
        assessment_status=assessment_status,
        indefinite_questionnaires=indefinite_questionnaires,
        OverallStatus=OverallStatus,
        full_name=user.display_name,
        comp_date=comp_date)
    complete_block = render_template(
        "eproms/assessment_engine/ae_complete.html",
        assessment_status=assessment_status,
        OverallStatus=OverallStatus,
        full_name=user.display_name,
        comp_date=comp_date)
    not_available_block = render_template(
        "eproms/assessment_engine/ae_not_available.html",
        full_name=user.display_name,
    )
    return render_template(
        "eproms/assessment_engine.html",
        user=user,
        assessment_status=assessment_status,
        indefinite_questionnaires=indefinite_questionnaires,
        OverallStatus=OverallStatus,
        thankyou_block=thankyou_block,
        indefinite_due_block=indefinite_due_block,
        due_block=due_block,
        complete_block=complete_block,
        not_available_block=not_available_block
    )


@eproms.route('/home')
def home():
    """home page view function

    Present user with appropriate view dependent on roles.

    The initial flow through authentication and data collection is
    controlled by next_after_login().  Only expecting requests
    here after login and intermediate steps have been handled, and then
    only if the login didn't include a 'next' target.

    Raising server error (500) if unexpected state is found to assist in
    finding problems.

    """
    user = current_user()

    # Enforce flow - expect authorized user for this view
    if not user:
        return redirect(url_for('eproms.landing'))

    # Possible user attempted to avoid flow via browser back
    # and needs to be sent immediately back to appropriate page
    if (not Coredata().initial_obtained(user) or
            'next' in session and session['next']):
        return next_after_login()

    # All checks passed - present appropriate view for user role
    if user.has_role(ROLE.STAFF_ADMIN.value):
        return redirect(url_for('staff.staff_index'))
    if user.has_role(
            ROLE.INTERVENTION_STAFF.value,
            ROLE.STAFF.value):
        return redirect(url_for('patients.patients_root'))
    if user.has_role(ROLE.CLINICIAN.value):
        return redirect(url_for('patients.patients_substudy'))
    if user.has_role(ROLE.RESEARCHER.value):
        return redirect(url_for('portal.research_dashboard'))

    interventions = Intervention.query.order_by(
        Intervention.display_rank).all()

    consent_agreements = {}
    return render_template(
        'eproms/portal.html',
        user=user,
        assessment_engine_view=assessment_engine_view,
        interventions=interventions,
        consent_agreements=consent_agreements)


@eproms.route('/privacy')
def privacy():
    """ privacy use page"""
    user = current_user()
    if user:
        organization = user.first_top_organization()
        role = None
        for r in (ROLE.STAFF.value, ROLE.PATIENT.value):
            if user.has_role(r):
                role = r
        # only include role and organization if both are defined
        if not all((role, organization)):
            role, organization = None, None

        privacy_resource = VersionedResource(app_text(
            PrivacyATMA.name_key(role=role, organization=organization)),
            locale_code=user.locale_code)
    else:
        abort(400, "No publicly viewable privacy policy page available")

    return render_template(
        'eproms/privacy.html',
        content=privacy_resource.asset, user=user,
        editorUrl=privacy_resource.editor_url)


@eproms.route('/terms')
def terms_and_conditions():
    """ terms-and-conditions of use page"""
    user = current_user()
    if user:
        organization = user.first_top_organization()
        role = None
        if user.has_role(ROLE.STAFF.value, ROLE.STAFF_ADMIN.value):
            role = ROLE.STAFF.value
        elif user.has_role(ROLE.PATIENT.value):
            role = ROLE.PATIENT.value
        if not all((role, organization)):
            role, organization = None, None

        terms = VersionedResource(app_text(Terms_ATMA.name_key(
            role=role, organization=organization)),
            locale_code=user.locale_code)
    else:
        terms = VersionedResource(
            app_text(Terms_ATMA.name_key()), locale_code=None)
    return render_template(
        'eproms/terms.html', content=terms.asset, editorUrl=terms.editor_url,
        user=user)


@eproms.route('/about')
def about():
    """main TrueNTH about page"""
    user = current_user()
    locale_code = user.locale_code if user else None
    about_tnth = VersionedResource(
        app_text(AboutATMA.name_key(subject='TrueNTH')),
        locale_code=locale_code)
    return render_template(
        'eproms/about.html',
        about_tnth=about_tnth.asset,
        about_tnth_editorUrl=about_tnth.editor_url,
        user=user)


@eproms.route('/contact', methods=('GET', 'POST'))
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
            'eproms/contact.html', sendername=sendername, email=email,
            user=user,
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


@eproms.route('/website-consent-script/<int:patient_id>', methods=['GET'])
@roles_required([ROLE.STAFF.value, ROLE.STAFF_ADMIN.value])
@oauth.require_oauth()
def website_consent_script(patient_id):
    entry_method = request.args.get('entry_method', None)
    redirect_url = request.args.get('redirect_url', None)
    if redirect_url:
        """
        redirect url here is the patient's assessment link
        /api/present-assessment, so validate against local origin
        """
        validate_origin(redirect_url)
    user = current_user()
    patient = get_user(patient_id, 'view')
    org = patient.first_top_organization()
    """
    NOTE, we are getting PATIENT's website consent terms here
    as STAFF member needs to read the terms to the patient
    """
    terms = get_terms(user.locale_code, org, ROLE.PATIENT.value)
    top_org = patient.first_top_organization()
    declaration_form = VersionedResource(
        app_text(WebsiteDeclarationForm_ATMA.name_key(organization=top_org)),
        locale_code=user.locale_code)
    return render_template(
        'eproms/website_consent_script.html', user=user,
        terms=terms, top_organization=top_org,
        entry_method=entry_method, redirect_url=redirect_url,
        declaration_form=declaration_form, patient_id=patient_id)


@eproms.route('/resources', methods=['GET'])
@roles_required([ROLE.STAFF.value, ROLE.STAFF_ADMIN.value])
@oauth.require_oauth()
def resources():
    user = current_user()
    org = user.first_top_organization()
    if not org:
        abort(400, 'user must belong to an organization')
    resources_data = get_any_tag_data(
        '{} work instruction'.format(org.name.lower()))
    results = resources_data['results']
    if (len(results) > 0):
        demo_content = []
        for asset in results:
            if 'demo' in asset['tags']:
                demo_content.append(asset_by_uuid(asset['uuid']))

        return render_template('eproms/resources.html',
                               results=results, demo_content=demo_content)
    else:
        abort(400, 'no resources found')


@eproms.route('/resources/work-instruction/<string:tag>', methods=['GET'])
@roles_required([ROLE.STAFF.value, ROLE.STAFF_ADMIN.value])
@oauth.require_oauth()
def work_instruction(tag):
    user = current_user()
    org = user.first_top_organization()
    if not tag:
        abort(400, 'work instruction tag is required')
    if not org:
        abort(400, 'user must belong to an organization')
    work_instruction_data = get_all_tag_data(tag, '{} work instruction'.
                                             format(org.name.lower()))
    results = work_instruction_data['results']
    if len(results) > 0:
        content = asset_by_uuid(results[0]['uuid'])
        return render_template('eproms/work_instruction.html',
                               content=content, title=tag)
    else:
        abort(400, 'work instruction not found')
