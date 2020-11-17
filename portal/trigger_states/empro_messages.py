"""Module to encapsulate EMPRO messaging details"""
from datetime import datetime
from flask import current_app, url_for

from portal.models.app_text import MailResource, app_text
from portal.models.communication import EmailMessage, load_template_args
from portal.models.user import User
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
        name = 'patient empro both triggers email'
    elif soft_triggers:
        name = 'patient empro soft triggers email'
    else:
        name = 'patient empro thank you email'
    mr = MailResource(
        app_text(name), locale_code=patient.locale_code, variables=args)
    em = EmailMessage(
        recipients=patient.email,
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        subject=mr.subject,
        body=mr.body)
    return em


def staff_emails(patient, hard_triggers):
    """Return list of emails, one for each eligible staff/clinician"""
    clinician = User.query.get(patient.clinician_id)
    # TODO lookup 'site coordinator' and copy
    # TODO plug in real app_text name for yet pending 'staff trigger email'

    # According to spec, args need at least:
    # - study ID
    # - link to patient profile
    # - list of `hard_triggers`
    args = {
        'study_id': patient.external_study_id,
        'patient_link': url_for(
            'patients.patient_profile', patient_id=patient.id, _external=True),
        'hard_triggers': hard_triggers
    }
    mr = MailResource(
        app_text("staff trigger email"),
        locale_code=patient.locale_code,
        variables=args)
    em = EmailMessage(
        recipients=clinician.email,
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        subject=mr.subject,
        body=mr.body)
    return em
