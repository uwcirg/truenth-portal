"""TN-1940 correct organization consent agreement_url for TNGR

Revision ID: d4517f61aaed
Revises: c1adb8e69b50
Create Date: 2020-02-12 10:58:18.851490

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.models.organization import Organization, OrgTree
from portal.models.user_consent import UserConsent

# revision identifiers, used by Alembic.
revision = 'd4517f61aaed'
down_revision = 'c1adb8e69b50'
Session = sessionmaker()


def upgrade():
    """replace incorrect user_consent.agreement_url for all TNGR child orgs"""
    bind = op.get_bind()
    session = Session(bind=bind)

    tngr = Organization.query.filter(
        Organization.name == "TrueNTH Global Registry").first()
    if not tngr:
        return

    ot = OrgTree()
    orgs = ot.here_and_below_id(tngr.id)

    new_agreement = (
        'https://eproms.truenth.org/legal/stock-org-consent/'
        'TrueNTH%20Global%20Registry')
    change_ids = [uc.id for uc in UserConsent.query.filter(
        UserConsent.organization_id.in_(orgs)).filter(
        UserConsent.agreement_url != new_agreement)]
    print("found {} needing updates".format(len(change_ids)))
    for i in change_ids:
        uc = session.query(UserConsent).get(i)
        uc.agreement_url = new_agreement
    session.commit()


def downgrade():
    # no value in restoring bogus data
    pass
