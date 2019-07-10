"""Hide existing sexual recovery patients and partners

Revision ID: c242e22f5a47
Revises: 29ddc9e0f61d
Create Date: 2019-07-09 15:34:06.820410

"""

from alembic import op
from datetime import datetime
from sqlalchemy.sql import text

from portal.models.audit import lookup_version
from portal.models.user import NO_EMAIL_PREFIX

# revision identifiers, used by Alembic.
revision = 'c242e22f5a47'
down_revision = '29ddc9e0f61d'

userlist = (
    "select user_id, email "
    "from user_roles join users on users.id = user_id "
    "where role_id in (select id from roles "
    "where name in ( 'patient', 'partner')) "
    "and user_id in ( select user_id from user_interventions "
    "where intervention_id in "
    "(select id from interventions where name = 'sexual_recovery')) "
    "and deleted_id is null")


def upgrade():
    """Hide all the existing SR patients and partners by masking email"""
    conn = op.get_bind()
    admin_id = conn.execute(
        "SELECT id FROM users WHERE email='__system__'").fetchone()[0]
    query = conn.execute(userlist)
    results = query.fetchall()
    changed_user_ids = []
    for r in results:
        if r[1].startswith(NO_EMAIL_PREFIX):
            raise RuntimeError(
                "user {} email already masked, "
                "won't be able to downgrade".format(r[0]))

        email = NO_EMAIL_PREFIX + r[1]
        conn.execute(text(
            "UPDATE users SET email=:email WHERE id=:id"),
            email=email, id=r[0])
        changed_user_ids.append(r[0])

    # add audit data
    now = datetime.utcnow()
    version = lookup_version()
    for subject_id in changed_user_ids:
        conn.execute(text(
            "INSERT INTO audit (comment, user_id, subject_id, context, timestamp, version) "
            "VALUES (:comment, :user_id, :subject_id, :context, :timestamp, :version)"),
            comment="masked email at end of SR RCT",
            user_id=admin_id,
            subject_id=subject_id,
            context='user',
            timestamp=now,
            version=version)


def downgrade():
    """Remove email mask added in upgrade step"""
    conn = op.get_bind()
    query = conn.execute(userlist)
    results = query.fetchall()
    for r in results:
        if not r[1].startswith(NO_EMAIL_PREFIX):
            raise RuntimeError(
                "user {} email missing mask, "
                "can't downgrade".format(r[0]))

        email = r[1][len(NO_EMAIL_PREFIX):]
        conn.execute(text(
            "UPDATE users SET email=:email WHERE id=:id"),
            email=email, id=r[0])
