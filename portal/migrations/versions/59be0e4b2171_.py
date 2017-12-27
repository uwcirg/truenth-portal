from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.models.audit import Audit
from portal.models.user_consent import UserConsent


"""empty message

Revision ID: 59be0e4b2171
Revises: 875b743d457f
Create Date: 2017-12-08 12:32:43.612464

"""

# revision identifiers, used by Alembic.
revision = '59be0e4b2171'
down_revision = '875b743d457f'


Session = sessionmaker()


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    for consent in session.query(UserConsent):
        audit = consent.audit
        if audit and (audit.comment == "Adding consent agreement"):
            audit.comment = "Consent agreement {} signed".format(consent.id)
            session.add(audit)
    session.commit()


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    for audit in session.query(Audit).filter(Audit.comment != None):
        words = audit.comment.split()
        if (len(words) == 4) and (words[0] == 'Consent'):
            if (words[-1] == 'signed'):
                audit.comment = "Adding consent agreement"
                session.add(audit)
            elif (words[-1] == 'recorded'):
                session.delete(audit)
    session.commit()
