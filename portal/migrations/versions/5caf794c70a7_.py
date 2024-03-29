"""mask email for withdrawn; obtain details of messages sent to withdrawn users

Revision ID: 5caf794c70a7
Revises: 3c871e710277
Create Date: 2024-03-25 12:14:46.377931

"""
from alembic import op
import datetime
import sqlalchemy as sa
from flask import current_app
from sqlalchemy.orm import sessionmaker

from portal.models.audit import Audit
from portal.models.message import EmailMessage
from portal.models.organization import Organization, OrgTree
from portal.models.qb_timeline import QBT
from portal.models.user import User, WITHDRAWN_PREFIX, patients_query
from portal.models.user_consent import UserConsent, consent_withdrawal_dates

# revision identifiers, used by Alembic.
revision = '5caf794c70a7'
down_revision = '3c871e710277'

Session = sessionmaker()


def patients(admin):
    """return list of patients potentially affected by withdrawal bugs

    limited to IRONMAN, withdrawn, non-deleted patients
    """
    irnmn = Organization.query.filter(Organization.name == 'IRONMAN').first()
    if not irnmn:
        return

    irnmn_orgs = OrgTree().here_and_below_id(organization_id=irnmn.id)

    at_least_once_wd = UserConsent.query.filter(UserConsent.status == 'suspended').with_entities(
        UserConsent.user_id).distinct()
    return patients_query(
        acting_user=admin,
        include_test_role=False,
        filter_by_ids=[i[0] for i in at_least_once_wd],
        requested_orgs=irnmn_orgs).with_entities(User.id)


def audit_since_for_patient(patient):
    #version_pattern = '24.3.8'
    min_id = 864688  # last id on prod with version 23.12.11.2
    # ignore `assessment` audits, as that's primarily qb_timeline rebuilds
    # which all of these users had.
    audit_query = Audit.query.filter(Audit._context != 'assessment').filter(
        Audit.subject_id == patient.id).filter(Audit.id > min_id)
    if not audit_query.count():
        return
    for audit in audit_query:
        if audit.context == 'consent' and audit.comment.startswith('remove bogus'):
            continue
        print(audit)

def emails_since_for_patient(patient):
    """report details on any emails since upgrade sent for patient"""
    min_id = 140419  # last id on prod before update
    addr = patient.email
    email_by_addr = EmailMessage.query.filter(EmailMessage.recipients == addr).filter(
        EmailMessage.id > min_id)
    email_by_id = EmailMessage.query.filter(EmailMessage.recipient_id == patient.id).filter(
        EmailMessage.id > min_id)
    if not (email_by_addr.count() + email_by_id.count()):
        return
    ids_seen = set()

    deceased = "deceased" if patient.deceased_id is not None else ""
    print(f"Patient {patient.id} {patient.external_study_id} {deceased}")
    for email in email_by_addr:
        ids_seen.add(email.id)
        print(f"User {patient.id} {email}")
    for email in email_by_id:
        if email.id not in ids_seen:
            print(f"User {patient.id} {email}")


def confirm_withdrawn_row(patient, rs_id):
    """confirm a withdrawal row is in users qb_timeline for given research study"""
    count = QBT.query.filter(QBT.user_id == patient.id).filter(
        QBT.research_study_id == rs_id).filter(QBT.status == 'withdrawn').count()
    if count != 1:
        # look out for the one valid case, where user has zero timeline rows
        if QBT.query.filter(QBT.user_id == patient.id).filter(
                    QBT.research_study_id == rs_id).count() == 0:
            return

        raise ValueError(f"no (or too many) withdrawn row for {patient.id} {rs_id}")


def mask_withdrawn_user_email(session, patient, admin):
    if not patient.email_ready()[0]:
        # no need, already hidden
        return

    version = current_app.config.metadata['version']
    now = datetime.datetime.utcnow()
    def audit_insert(subject_id):
        msg = f"mask withdrawn user email"
        insert = (
            "INSERT INTO AUDIT"
            " (user_id, subject_id, context, timestamp, version, comment)"
            " VALUES"
            f"({admin.id}, {subject_id}, 'user',"
            f" '{now}', '{version}', '{msg}')")
        session.execute(insert)

    patient._email = WITHDRAWN_PREFIX + patient.email
    audit_insert(patient.id)


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    admin = session.query(User).filter_by(email='__system__').first()

    for pat_row in patients(admin):
        patient_id = pat_row[0]
        patient = session.query(User).get(patient_id)
        # confirm withdrawn status (global g or empro e)
        consent_g, withdrawal_g = consent_withdrawal_dates(patient, 0)
        consent_e, withdrawal_e = consent_withdrawal_dates(patient, 1)
        if not (withdrawal_e or withdrawal_g):
            continue

        if withdrawal_g:
            confirm_withdrawn_row(patient, 0)
        if withdrawal_e:
            confirm_withdrawn_row(patient, 1)

        # check for users consented for both but only withdrawn from one
        if (consent_g and consent_e) and not (withdrawal_g and withdrawal_e):
            # print(f"user {patient_id} consented for both, but only withdrawn from one")
            continue

        audit_since_for_patient(patient)
        emails_since_for_patient(patient)
        mask_withdrawn_user_email(session, patient, admin)
        session.commit()



def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
