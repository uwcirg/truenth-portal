"""Clean up user_consents.expires issue

Revision ID: 17060aa3c9d6
Revises: 2aa8089588bf
Create Date: 2022-12-28 05:08:10.714337

"""
from alembic import op
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.models.qb_timeline import update_users_QBT
from portal.models.questionnaire_response import QuestionnaireResponse
from portal.models.research_study import BASE_RS_ID
from portal.models.role import ROLE
from portal.models.user import User, unchecked_get_user
from portal.models.user_consent import UserConsent

# revision identifiers, used by Alembic.
revision = '17060aa3c9d6'
down_revision = '2aa8089588bf'

SessionMaker = sessionmaker()


def upgrade():
    """ The user_consents table has an expires field, given a default value
    of 5 years from the moment any user_content row is generated, and never
    touched again.

    Once user_consents.expires is eclipsed by current time, the user's
    timeline is incorrectly purged, as they no longer have a valid consent
    on file.  This field isn't being used as originally intended, and the
    QuestionnaireBank logic handles the end of a study correctly, thus
    user_consents.expires should be removed.

    But first, we need to restore timeline status for all users having
    passed the point of expiration.
    """
    session = SessionMaker(bind=op.get_bind())
    sys_user = User.query.filter_by(email='__system__').one()

    # Obtain a list of patients for whom their consent has expired
    now = datetime.utcnow()
    query = UserConsent.query.filter(UserConsent.expires < now).with_entities(
        UserConsent.user_id).distinct().order_by(UserConsent.user_id)
    for row in session.execute(query):
        user_id = row[0]
        user = unchecked_get_user(user_id, allow_deleted=True)
        if user.deleted_id or not user.has_role(ROLE.PATIENT.value):
            continue

        # Code modifications in place ignore expires, force a QB timeline
        # full rebuild
        QuestionnaireResponse.purge_qb_relationship(
            subject_id=user_id,
            research_study_id=BASE_RS_ID,
            acting_user_id=sys_user.id)

        update_users_QBT(
            user_id,
            research_study_id=BASE_RS_ID,
            invalidate_existing=True)

        print(f"Restored timeline for {user_id}")


def downgrade():
    # no downgrade for this migration
    pass
