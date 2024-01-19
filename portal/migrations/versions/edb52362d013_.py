"""Correct user_consent regression issues raised by PR #4343

Revision ID: edb52362d013
Revises: d1f3ed8d16ef
Create Date: 2024-01-11 16:23:34.961937

"""
from alembic import op
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.functions import count

from portal.models.research_study import BASE_RS_ID, EMPRO_RS_ID
from portal.models.qb_timeline import update_users_QBT
from portal.models.questionnaire_response import (
    capture_patient_state,
    present_before_after_state,
)
from portal.models.user_consent import UserConsent

# revision identifiers, used by Alembic.
revision = 'edb52362d013'
down_revision = 'd1f3ed8d16ef'

Session = sessionmaker()


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

    for study_id in (BASE_RS_ID, EMPRO_RS_ID):

        subquery = session.query(UserConsent.user_id).distinct().filter(
            UserConsent.research_study_id == study_id).filter(
            UserConsent.status == 'suspended').subquery()
        query = session.query(
            count(UserConsent.user_id), UserConsent.user_id).filter(
            UserConsent.research_study_id == study_id).filter(
            UserConsent.user_id.in_(subquery)).group_by(
            UserConsent.user_id).having(count(UserConsent.user_id) > 2)
        for num, patient_id in query:
            b4_state = capture_patient_state(patient_id)
            update_users_QBT(
                patient_id,
                research_study_id=study_id,
                invalidate_existing=True)
            present_before_after_state(
                patient_id, study_id, b4_state)

    raise NotImplemented('finish me')


def downgrade():
    """no downgrade available"""
    pass
