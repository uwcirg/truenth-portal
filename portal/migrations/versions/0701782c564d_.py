"""Correct user_consents on deceased patients

Revision ID: 0701782c564d
Revises: 1d84237ed07c
Create Date: 2019-03-28 12:16:06.567817

"""
import logging

from portal.database import db
from portal.models.audit import Audit
from portal.models.qb_timeline import invalidate_users_QBT
from portal.models.user import User
from portal.models.user_consent import (
    INCLUDE_IN_REPORTS_MASK,
    SEND_REMINDERS_MASK,
    STAFF_EDITABLE_MASK,
    UserConsent,
)

# revision identifiers, used by Alembic.
revision = '0701782c564d'
down_revision = '1d84237ed07c'

log = logging.getLogger("alembic")
log.setLevel(logging.DEBUG)


def patch_deceased_user_consents(uid):
    user = User.query.get(uid)
    user_consents = UserConsent.query.filter(
        UserConsent.user_id == uid).order_by(UserConsent.id).all()

    # if no user_consents exist for user, we're done
    if not user_consents:
        return

    # acquire the deceased date
    dd = user.deceased.timestamp

    # if the most recent consent looks correct, assume we're done
    if user_consents[-1].status == 'suspended' and not(
            user_consents[-1].options & SEND_REMINDERS_MASK):
        return

    admin = User.query.filter_by(email='__system__').first()

    log.info("Patching broken consents for {}, with deceased date {}".format(
        user, dd))
    keeper = user_consents.pop(0)
    log.info(" keeping original user_consent {} {} {} {}".format(
        keeper.id, keeper.status, keeper.options, keeper.acceptance_date))
    obsolete_audits, obsolete_consents = [], []
    for uc in user_consents:
        log.info(" deleting user_consent {} {} {} {}".format(
            uc.id, uc.status, uc.options, uc.acceptance_date))
        a = Audit.query.get(uc.audit_id)
        log.info("  and the related {}".format(a))
        obsolete_audits.append(a.id)
        obsolete_consents.append(uc.id)

    # out of loop, delete the unwanted
    db.session.query(UserConsent).filter(UserConsent.id.in_(
        obsolete_consents)).delete(synchronize_session=False)
    db.session.query(Audit).filter(Audit.id.in_(
        obsolete_audits)).delete(synchronize_session=False)
    db.session.commit()

    # now add back in the corrected consent, from the initial
    deceased_options = STAFF_EDITABLE_MASK | INCLUDE_IN_REPORTS_MASK
    deceased_consent = UserConsent(
        user_id=uid,
        organization_id=keeper.organization_id,
        agreement_url=keeper.agreement_url,
        acceptance_date=dd,
        options=deceased_options,
        status='suspended')

    user.update_consents(
        consent_list=[deceased_consent], acting_user=admin)

    # The updated consent may have altered the cached assessment
    # status - invalidate this user's data at this time.
    invalidate_users_QBT(user_id=user.id)
    db.session.commit()

    log.info(" Done, results:")
    for uc in UserConsent.query.filter(UserConsent.user_id == uid):
        log.info("  {} {} {} {}".format(
            uc, uc.acceptance_date, uc.status, uc.options))


def upgrade():
    """Correct user_consents for any deceased patients found in error

    Deceased patients should get a fresh user consent with status = suspended
    and options updated to disable send_reminders.

    """
    deceased_users = [id[0] for id in User.query.filter(
        User.deceased_id.isnot(None)).filter(
        User.deleted_id.is_(None)).with_entities(User.id)]
    log.info("found {} deceased users: {}".format(
        len(deceased_users), deceased_users))

    for uid in deceased_users:
        patch_deceased_user_consents(uid)


def downgrade():
    """Don't try and restore the broken..."""
    pass
