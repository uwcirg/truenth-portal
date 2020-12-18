"""Module to encapsulate EMPRO messaging details"""
from datetime import datetime
from flask import current_app, url_for
from flask_babel import gettext as _

from portal.models.app_text import MailResource, app_text
from portal.models.communication import EmailMessage, load_template_args
from portal.models.organization import UserOrganization
from portal.models.role import ROLE, Role
from portal.models.user import User, UserRoles
from portal.models.qb_status import QB_Status


def patient_email(patient, soft_triggers, hard_triggers):
    """Prepare email for patient, depending on trigger status"""

    # If the user has a pending questionnaire bank, include for due date
    qstats = QB_Status(
        patient,
        research_study_id=1,
        as_of_date=datetime.utcnow())
    qbd = qstats.current_qbd()
    if qbd:
        qb_id, qb_iteration = qbd.qb_id, qbd.iteration
    else:
        qb_id, qb_iteration = None, None

    args = load_template_args(
        user=patient, questionnaire_bank_id=qb_id, qb_iteration=qb_iteration)

    if hard_triggers:
        name = 'empro patient both triggers email'
    elif soft_triggers:
        name = 'empro patient soft triggers email'
    else:
        name = 'empro patient thank you email'
    mr = MailResource(
        app_text(name), locale_code=patient.locale_code, variables=args)
    em = EmailMessage(
        recipients=patient.email,
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        subject=mr.subject,
        body=mr.body)
    return em


def staff_emails(patient, hard_triggers, initial_notification):
    """Return list of emails, one for each eligible staff/clinician"""

    # Only supporting patients with a single organization
    if len(patient.organizations) != 1:
        raise ValueError(
            f"Require single org on patient {patient.id} ")
    org_id = patient.organizations[0].id

    # Email every clinician and staff (not staff-admin) directly
    # associated with the patient's organization

    staff_list = User.query.join(UserRoles).filter(
        User.id == UserRoles.user_id).join(Role).filter(
        UserRoles.role_id == Role.id).filter(
        Role.name.in_((ROLE.STAFF.value, ROLE.CLINICIAN.value))).join(
        UserOrganization).filter(
        User.id == UserOrganization.user_id).filter(
        UserOrganization.organization_id == org_id)

    # make sure assigned clinician made the list
    found = [user.id for user in staff_list if user.id == patient.clinician_id]
    if not found:
        raise ValueError(
            f"Patient's ({patient.id}) assigned clinician not in distribution"
            f" list. Check clinician's ({patient.clinician_id}) organization")

    app_text_name = 'empro clinician trigger reminder'
    if initial_notification:
        app_text_name = 'empro clinician trigger notification'

    # According to spec, args need at least:
    # - study ID
    # - link to patient profile
    # - list of `hard_triggers`
    clinic = ''
    if patient.organizations:
        clinic = _(patient.organizations[0].name)
    link = (
        '<a href={href} '
        'style="font-size: 0.9em; '
        'font-family: Helvetica, Arial, sans-serif; '
        'display: inline-block; color: #FFF; '
        'background-color: #7C959E; border-color: #7C959E; '
        'border-radius: 0; '
        'letter-spacing: 2px; cursor: pointer; '
        'text-transform: uppercase; text-align: center; '
        'line-height: 1.42857143; '
        'font-weight: 400; padding: 0.6em; text-decoration: none;">'
        '{label}</a>'.format(href=url_for(
            'patients.patient_profile',
            patient_id=patient.id,
            _anchor='postInterventionQuestionnaireLoc',
            _external=True),
            label=_('View Participant Details')))
    args = {
        'clinic_name': clinic,
        'patient_id': patient.id,
        'post_intervention_assessment_link': link,
        'triggered_domains': hard_triggers
    }
    emails = []
    for staff in staff_list:
        mr = MailResource(
            app_text(app_text_name),
            locale_code=staff.locale_code,
            variables=args)
        emails.append(EmailMessage(
            recipients=staff.email,
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            subject=mr.subject,
            body=mr.body))
    return emails
