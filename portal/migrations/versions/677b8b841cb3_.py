"""Add recipient_id to email_messages table and populate

Revision ID: 677b8b841cb3
Revises: da6506c5899a
Create Date: 2019-10-23 11:36:41.947859

"""
from alembic import op
import logging
import re
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

from portal.models.audit import Audit
from portal.models.message import EmailMessage
from portal.models.user import User

# revision identifiers, used by Alembic.
revision = '677b8b841cb3'
down_revision = 'da6506c5899a'

logger = logging.getLogger("alembic")
Session = sessionmaker()


def upgrade():
    op.add_column(
        'email_messages',
        sa.Column('recipient_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'email_messages_recipient_id_fkey',
        'email_messages',
        'users',
        ['recipient_id'],
        ['id'],
        ondelete='CASCADE')

    session = Session(bind=op.get_bind())
    # Email messages generate an audit row, holding the subject_id.
    # Build a dictionary for lookup below when the current email doesn't match
    old_address_dict = dict()
    for adt in session.query(Audit).filter(Audit.comment.like('EmailMessage %')):
        finds = re.match(
            r"EmailMessage\ .*?sent\ to\ (.*?)\ from .*", adt.comment)
        if finds.groups():
            old_address_dict[finds.groups()[0].lower()] = adt.subject_id

    # nested query kills runtime - cache current user-email list
    emails_to_user_id = dict()
    for u in session.query(User).filter(
            User.deleted_id.is_(None)).with_entities(User.id, User.email):
        emails_to_user_id[u.email.lower()] = u.id

    # Populate the recipient_id as best we can.
    # SQLA doesn't like changes inside a query - store intent in dict
    change_em = dict()
    for em in session.query(EmailMessage).filter(
            EmailMessage.recipients != 'help.truenthusa@movember.com'):
        if ',' in em.recipients:
            raise ValueError("can't handle multiple recipients")

        # always use lowercase addresses for comparison
        recipients = em.recipients.lower()

        # First, eliminate all that have a matching current email
        if recipients in emails_to_user_id:
            change_em[em.id] = emails_to_user_id[recipients]
            continue

        # Next, see if address can be found in the old_address_dict
        if recipients in old_address_dict:
            change_em[em.id] = old_address_dict[recipients]
            continue

        logging.warning("no match for {} to {}".format(
            em.subject, em.recipients))

    logging.info("found {} gaining recipient_id".format(len(change_em)))
    conn = op.get_bind()
    for email_message_id, recipient_id in change_em.items():
        stmt = (
            "UPDATE email_messages SET recipient_id=:recipient_id "
            "WHERE id=:email_message_id")
        conn.execute(
            text(stmt),
            email_message_id=email_message_id,
            recipient_id=recipient_id)


def downgrade():
    op.drop_constraint(
        'email_messages_recipient_id_fkey',
        'email_messages', type_='foreignkey')
    op.drop_column('email_messages', 'recipient_id')
