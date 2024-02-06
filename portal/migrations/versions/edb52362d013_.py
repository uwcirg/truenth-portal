"""Remove/correct bogus user_consents as per IRONN-210

Revision ID: edb52362d013
Revises: 66368e673005
Create Date: 2024-01-11 16:23:34.961937

"""
from alembic import op
from datetime import datetime
from flask import current_app
from sqlalchemy.orm import sessionmaker

from portal.models.user_consent import UserConsent

# revision identifiers, used by Alembic.
revision = 'edb52362d013'
down_revision = '66368e673005'

Session = sessionmaker()


def user_consent_manual_cleanup(session):
    # turned into a detailed situation, of obtaining original dates from MR
    # and correcting a number of bogus rows in the user_consent table.
    # This hand curated list comes from attachments in
    # https://movember.atlassian.net/browse/IRONN-210
    # run these first, then confirm everything looks clean.
    now = datetime.utcnow()
    version = current_app.config.metadata['version']

    admin_id = session.execute(
        "SELECT id FROM users WHERE email = '__system__'"
    ).next()[0]

    def audit_insert(subject_id, user_consent_id, acceptance_date=None):
        msg = f"remove bogus user_consent {user_consent_id} per IRONN-210"
        if acceptance_date:
            msg = f"corrected user_consent {user_consent_id} to {acceptance_date} per IRONN-210"
        print(msg)
        insert = (
            "INSERT INTO AUDIT"
            " (user_id, subject_id, context, timestamp, version, comment)"
            " VALUES"
            f"({admin_id}, {subject_id}, 'consent',"
            f" '{now}', '{version}', '{msg}')")
        session.execute(insert)

    def delete_user_consent(user_id, user_consent_id):
        return UserConsent.query.filter(
            UserConsent.id == user_consent_id).filter(
            UserConsent.user_id == user_id).delete()

    def update_user_consent(user_id, user_consent_id, acceptance_date):
        uc = UserConsent.query.filter(
            UserConsent.id == user_consent_id).filter(
            UserConsent.user_id == user_id).one()
        uc.acceptance_date = acceptance_date

    bogus_values = [
        {'user_id': 101, 'user_consent_id': 219},
        {'user_id': 145, 'user_consent_id': 1238},
        {'user_id': 164, 'user_consent_id': 218},
        {'user_id': 224, 'user_consent_id': 211},
        {'user_id': 310, 'user_consent_id': 1200},
        {'user_id': 4316, 'user_consent_id': 5033},
        {'user_id': 4316, 'user_consent_id': 5032},
        {'user_id': 98, 'user_consent_id': 339},
        {'user_id': 774, 'user_consent_id': 897},
    ]

    correct_values = []
    #    {'user_id': 719, 'user_consent_id': 544, 'acceptance_date': '2018/05/29 00:00:00'},
    #    {'user_id': 723, 'user_consent_id': 551, 'acceptance_date': '2018/05/16 00:00:00'},
    #]
    for row in correct_values:
        update_user_consent(
            user_id=row['user_id'],
            user_consent_id=row['user_consent_id'],
            acceptance_date=row['acceptance_date'])
        audit_insert(
            subject_id=row['user_id'],
            user_consent_id=row['user_consent_id'],
            acceptance_date=row['acceptance_date'])
        session.commit()

    for row in bogus_values:
        if  delete_user_consent(
            user_id=row['user_id'],
            user_consent_id=row['user_consent_id']):
            audit_insert(
                subject_id=row['user_id'],
                user_consent_id=row['user_consent_id'])
            session.commit()


def upgrade():
    """Correct UserConsents for any negatively affected patients

    Prior to the release of 23.10.12.1, moving withdrawal dates wasn't
    allowed. This made lookups for the last valid user_consent *prior*
    to the withdrawal date, reliable, as user_consents land in the table
    in an ordered fashion, and the most recently deleted prior to
    withdrawal would have been in use.

    The implementation of IRONN-210 enabled moving of withdrawal dates,
    and incorrectly assumed it would be necessary to allow lookups of
    the previous valid consent, to just work further back in the stack
    of user_consents.  That would only be correct on the few tested,
    where the user didn't have multiple user_consents on file prior to
    withdrawal.

    To enable moving withdrawal dates, user_consents now allow multiple
    of status "suspended", with the most recent by id taking precedence.
    To determine the valid consent in use prior to withdrawal, look back
    by insertion order (id) for the first deleted user consent prior to
    status "suspended".

    With code changes in place, migration must simply locate any potential
    consent changes since the error was introduced and recalculate timeline
    """
    # turns out, we have no reliable mechanism to determine which patients
    # may have been affected, as the acceptance date on withdrawn was simply
    # changed on the already withdrawn user_consent, and no audit of the
    # modification was recorded.  need to try a recalc and find persist
    # any changes for any users with a suspended user_consent and more
    # than two (the original valid consent plus the suspended one) on
    # any given research study.
    bind = op.get_bind()
    session = Session(bind=bind)

    user_consent_manual_cleanup(session)
    session.commit()


def downgrade():
    """no downgrade available"""
    pass
