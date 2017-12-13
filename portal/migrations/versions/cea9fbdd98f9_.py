from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.models.communication_request import CommunicationRequest
from portal.models.identifier import Identifier
from portal.system_uri import TRUENTH_CR_NAME


"""Correct IRONMAN 6 month iteration count

Revision ID: cea9fbdd98f9
Revises: 72dcf1946d3f
Create Date: 2017-12-13 13:57:59.215573

"""

# revision identifiers, used by Alembic.
revision = 'cea9fbdd98f9'
down_revision = '72dcf1946d3f'

Session = sessionmaker()


def upgrade():
    # Correct the iteration count for the existing IRONMAN 6 month
    # communication requests (need to start at index 0, not 1)
    # Necessary to do as a migration, otherwise we break FK constraints
    bind = op.get_bind()
    session = Session(bind=bind)
    idents = session.query(Identifier).filter(
        Identifier.system == TRUENTH_CR_NAME).filter(
        Identifier._value.like(u'IRONMAN Recurring | 6 Month %'))
    for id in idents:
        cr = CommunicationRequest.find_by_identifier(id)
        # bring into *this* session
        cr = session.query(CommunicationRequest).get(cr.id)
        cr.qb_iteration = 0
    session.commit()

def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    idents = session.query(Identifier).filter(
        Identifier.system == TRUENTH_CR_NAME).filter(
        Identifier._value.like(u'IRONMAN Recurring | 6 Month %'))
    for id in idents:
        cr = CommunicationRequest.find_by_identifier(id)
        # bring into *this* session
        cr = session.query(CommunicationRequest).get(cr.id)
        cr.qb_iteration = 1
    session.commit()
