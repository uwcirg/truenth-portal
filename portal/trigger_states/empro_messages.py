"""Module to encapsulate EMPRO messaging details"""
from datetime import datetime
from flask import current_app, url_for
from flask_babel import gettext as _
from smtplib import SMTPRecipientsRefused

from portal.database import db
from portal.models.app_text import MailResource, app_text
from portal.models.communication import EmailMessage, load_template_args
from portal.models.organization import UserOrganization
from portal.models.role import ROLE, Role
from portal.models.user import User, UserRoles
from portal.models.qb_status import QB_Status


def invite_email(user):
    if not user.email_ready():
        current_app.logger.error(f"{user.id} can't receive EMPRO invite email")
        return
    args = load_template_args(user=user)
    item = MailResource(
        app_text("patient invite email IRONMAN EMPRO Study"),
        locale_code=user.locale_code,
        variables=args)
    msg = EmailMessage(
        subject=item.subject,
        body=item.body,
        recipients=user.email,
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        user_id=user.id)
    try:
        msg.send_message()
    except SMTPRecipientsRefused as exc:
        current_app.logger.error(
            "Error sending EMPRO Invite to %s: %s",
            user.email, exc)
    db.session.add(msg)


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
        recipient_id=patient.id,
        recipients=patient.email,
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        subject=mr.subject,
        body=mr.body)
    return em


def staff_emails(patient, hard_triggers, opted_out_domains, initial_notification):
    """Return list of emails, one for each eligible staff/clinician"""

    # Only supporting patients with a single organization
    if len(patient.organizations) != 1:
        raise ValueError(
            f"Require single org on patient {patient.id} ")
    org_id = patient.organizations[0].id

    # Email every staff (not staff-admin) directly
    # associated with the patient's organization

    staff_list = [
        user for user in User.query.join(UserRoles).filter(
        User.id == UserRoles.user_id).join(Role).filter(
        UserRoles.role_id == Role.id).filter(
        Role.name == ROLE.STAFF.value).join(
        UserOrganization).filter(
        User.id == UserOrganization.user_id).filter(
        UserOrganization.organization_id == org_id).filter(
        User.deleted_id.is_(None))]

    # Add (if not already present from staff query) the assigned clinician(s)
    staff_list_ids = set([user.id for user in staff_list])
    for c in patient.clinicians:
        if c.id not in staff_list_ids:
            staff_list.append(c)

    # opt-in holds hard triggers the user did NOT opt-out of
    opt_in_domains = hard_triggers

    app_text_name = 'empro clinician trigger reminder'
    if initial_notification:
        app_text_name = 'empro clinician trigger notification'
    if not (set(hard_triggers) - set(opted_out_domains)):
        # All triggered were opted out of - pick up different email template
        app_text_name += " all opted out"
        opt_in_domains = []
        if not initial_notification:
            # seen on test, no idea how - include details in exception
            msg = (f"Patient {patient.id} all opted out: {opted_out_domains} "
                   f"shouldn't be eligible for a reminder!")
            current_app.logger.error(msg)
            app_text_name = 'empro clinician trigger notification all opted out'
    elif opted_out_domains:
        app_text_name += " partially opted out"
        opt_in_domains = list(set(hard_triggers) - set(opted_out_domains))

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
    opted_out = ", ".join(opted_out_domains) if opted_out_domains else ""
    opted_out_display = "<b>{opted_out}</b>".format(opted_out=opted_out)
    triggered_domains = ", ".join(opt_in_domains) if opt_in_domains else ""
    triggered_domains_display = "<b>{triggered_domains}</b>".format(
        triggered_domains=triggered_domains)
    args = {
        'clinic_name': clinic,
        'patient_id': patient.id,
        'study_id': patient.external_study_id,
        'post_intervention_assessment_link': link,
        'opted_out': opted_out_display,
        'triggered_domains': triggered_domains_display
    }
    emails = []
    for staff in staff_list:
        if not staff.email_ready()[0]:
            current_app.logger.error(f"can't email staff {staff} without email")
            continue
        mr = MailResource(
            app_text(app_text_name),
            locale_code=staff.locale_code,
            variables=args)
        emails.append(EmailMessage(
            recipient_id=staff.id,
            recipients=staff.email,
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            subject=mr.subject,
            body=mr.body))
    return emails
