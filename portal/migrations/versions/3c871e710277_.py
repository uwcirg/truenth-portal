"""Correct user_consent regression issues raised by PR #4343

Revision ID: 3c871e710277
Revises: edb52362d013
Create Date: 2024-01-25 20:04:48.109980

"""
from alembic import op
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.functions import count

from portal.cache import cache
from portal.models.research_study import BASE_RS_ID, EMPRO_RS_ID
from portal.models.qb_timeline import update_users_QBT
from portal.models.questionnaire_bank import trigger_date
from portal.models.questionnaire_response import (
    QuestionnaireResponse,
    capture_patient_state,
    present_before_after_state,
)
from portal.models.user import User
from portal.models.user_consent import UserConsent, consent_withdrawal_dates
from portal.timeout_lock import ADHERENCE_DATA_KEY, CacheModeration

Session = sessionmaker()


# revision identifiers, used by Alembic.
revision = '3c871e710277'
down_revision = 'edb52362d013'


# csv values direct from attachment in #IRONN-210, used to verify
verified_user_consent_dates = (
    {
        101: ("13-Dec-17", "13-Dec-17"),
        1073: ("16-Nov-18", "19-Sep-23"),
        1113: ("24-Oct-18", "27-Oct-21"),
        1186: ("19-Dec-18", "19-Dec-18"),
        1229: ("14-Jan-19", "10-Jan-24"),
        145: ("11-Jan-18", "17-Oct-18"),
        1524: ("12-Mar-19", "28-Oct-21"),
        1608: ("2-Apr-19", "7-Jun-21"),
        164: ("8-Jan-18", "7-Mar-18"),
        184: ("2-Feb-18", "2-May-19"),
        2049: ("4-Jul-19", "1-Jun-22"),
        209: ("22-Feb-18", "14-Dec-20"),
        224: ("28-Feb-18", "9-Mar-18"),
        2425: ("18-Sep-19", "26-May-21"),
        2547: ("25-Sep-19", "4-Aug-21"),
        2748: ("19-Nov-19", "22-Oct-22"),
        2845: ("23-Aug-19", "23-Sep-21"),
        2911: ("27-Nov-19", "9-Sep-23"),
        310: ("12-Apr-18", "16-Aug-18"),
        3251: ("16-Mar-20", "19-Jan-22"),
        3256: ("19-Mar-20", "5-May-22"),
        3427: ("26-May-20", "2-Sep-22"),
        3430: ("16-Jun-20", "15-May-21"),
        3455: ("4-Jun-20", "7-May-21"),
        3826: ("11-Nov-20", "30-Nov-20"),
        4316: ("19-Apr-21", "27-Apr-22"),
        4806: ("17-Feb-22", "13-Oct-22"),
        482: ("8-Aug-17", "28-Jul-20"),
        4861: ("28-Sep-21", "27-Feb-22"),
        4868: ("3-Mar-22", "18-Aug-22"),
        5004: ("5-Oct-21", "24-Sep-23"),
        5336: ("31-Jan-22", "7-Nov-23"),
        5852: ("5-Jul-22", "15-Apr-23"),
        5853: ("5-Jul-22", "20-Apr-23"),
        5959: ("26-Jul-22", "17-Aug-22"),
        6204: ("17-Sep-22", "25-Oct-23"),
        6218: ("27-Sep-22", "29-Oct-23"),
        641: ("7-Aug-18", "29-Dec-20"),
        653: ("9-Jul-18", "10-Sep-18"),
        6686: ("29-Jan-23", "12-Jun-23"),
        # 719: ("29-May-18", "27-Aug-18"),  as per story, leave alone
        # 723: ("16-May-18", "25-Aug-23"),  as per story, leave alone
        774: ("24-Oct-17", "9-Nov-17"),
        833: ("12-Sep-18", "11-Sep-23"),
        892: ("18-Sep-18", "5-Jan-20"),
        98: ("13-Dec-17", "22-Mar-18"),
        986: ("6-Sep-18", "22-Jun-23"),
        987: ("26-Jul-18", "14-Oct-19"),
    },
    {
        563: ("10-Nov-22", "16-Dec-22"),
        3591: ("1-Oct-22", "1-Oct-23"),
        5596: ("12-Jul-22", "12-Oct-22"),
        5747: ("6-Jun-22", "10-Jun-23"),
        5849: ("5-Jul-22", "12-Oct-22"),
        6026: ("4-Nov-22", "4-Nov-23"),
    }
)


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
        # due to changes in adherence report for withdrawn users
        # this query is now simply any withdrawn patient who isn't
        # deleted from the system.
        subquery = session.query(User.id).filter(
            User.deleted_id.is_(None)).subquery()
        query = session.query(UserConsent.user_id.distinct()).filter(
            UserConsent.research_study_id == study_id).filter(
            UserConsent.status == "suspended").filter(
            UserConsent.user_id.in_(subquery))

        for row in query:
            patient_id = row[0]
            if patient_id in (719, 1186, 1305):
                # special cases best left alone
                continue
            user = User.query.get(patient_id)
            consent_date, withdrawal_date = consent_withdrawal_dates(
                user, study_id)
            if withdrawal_date is None:
                # scenario happens with a withdrawn patient re-start
                # i.e. as withdrawal was entered in error.
                # no change needed in this situation
                continue

            # report if dates don't match spreadsheet in IRONN-210
            cd_str = '{dt.day}-{dt:%b}-{dt:%y}'.format(dt=consent_date)
            wd_str = '{dt.day}-{dt:%b}-{dt:%y}'.format(dt=withdrawal_date)
            try:
                match = verified_user_consent_dates[study_id][patient_id]
                if (cd_str, wd_str) != match:
                    print(f"user_id {patient_id} \t {cd_str} \t {wd_str}")
                    print(" vs expected:")
                    print(f"\t\t {match[0]} \t {match[1]}")
            except KeyError:
                # user found to not see timeline change
                pass

            # fake an adherence cache run to avoid unnecessary and more
            # important, to prevent from locking out a subsequent update
            # needed after recognizing a real change below
            adherence_cache_moderation = CacheModeration(key=ADHERENCE_DATA_KEY.format(
                patient_id=patient_id,
                research_study_id=study_id))
            adherence_cache_moderation.run_now()

            b4_state = capture_patient_state(patient_id)
            update_users_QBT(
                patient_id,
                research_study_id=study_id,
                invalidate_existing=True)
            _, _, _, any_changes = present_before_after_state(
                patient_id, study_id, b4_state)
            if not any_changes:
                continue

            print(f"{patient_id} changed, purge old adherence data and relationships")
            adherence_cache_moderation.reset()
            QuestionnaireResponse.purge_qb_relationship(
                subject_id=patient_id,
                research_study_id=study_id,
                acting_user_id=patient_id)
            cache.delete_memoized(trigger_date)
            update_users_QBT(
                patient_id,
                research_study_id=study_id,
                invalidate_existing=True)


def downgrade():
    """no downgrade available"""
    pass
