"""Capture email_message.recipient ID when missed on __invite__ prefix

Revision ID: df233cc6fa8a
Revises: 908731b85112
Create Date: 2019-12-12 16:13:54.058040

"""
from alembic import op
from sqlalchemy.orm import sessionmaker
from portal.models.message import EmailMessage
from portal.models.user import INVITE_PREFIX, User

# revision identifiers, used by Alembic.
revision = 'df233cc6fa8a'
down_revision = '908731b85112'
Session = sessionmaker()


def upgrade():
    session = Session(bind=op.get_bind())

    needing_attn = session.query(EmailMessage).filter(
        EmailMessage.recipient_id.is_(None))
    items = []  # don't update mid query
    for em in needing_attn:
        items.append({'id': em.id, 'recipients': em.recipients})

    # Whip through, updating those for which we can find a valid recipient
    corrected = 0
    for i in items:
        user = session.query(User).filter(
            User.email == i['recipients']).first()
        if not user:
            user = session.query(User).filter(User.email == "{}{}".format(
                INVITE_PREFIX, i['recipients'])).first()
        if user:
            em = session.query(EmailMessage).get(i['id'])
            em.recipient_id = user.id
            corrected += 1

    if corrected:
        session.commit()
        print(
            "Corrected {} EmailMessages of {} missing a recipient_id".format(
                corrected, len(items)))


def downgrade():
    # No downgrade needed
    pass
