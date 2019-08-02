"""2nd pass at adding IRONMAN 3 digit identifiers

Revision ID: 4ea2b79957f3
Revises: d561999e9b42
Create Date: 2019-04-30 12:17:03.382443

"""
import re

from alembic import op
from sqlalchemy.orm.session import Session

from portal.models.identifier import Identifier
from portal.models.organization import OrganizationIdentifier
from portal.models.user import UserIdentifier
from portal.system_uri import TRUENTH_EXTERNAL_STUDY_SYSTEM

# revision identifiers, used by Alembic.
revision = '4ea2b79957f3'
down_revision = 'd561999e9b42'

org_pattern = re.compile(r'^146-(\d\d)$')
study_pattern = re.compile(r'^170-(\d\d)-(\d\d\d)$')


def upgrade():
    session = Session(bind=op.get_bind(), expire_on_commit=False)

    # All IRONMAN orgs need a 3 digit version
    IRONMAN_system = 'http://pcctc.org/'

    ironman_org_ids = [(id.id, id._value) for id in Identifier.query.filter(
        Identifier.system == IRONMAN_system).with_entities(
        Identifier.id, Identifier._value)]
    existing_values = [id[1] for id in ironman_org_ids]

    replacements = {}
    for io_id, io_value in ironman_org_ids:
        found = org_pattern.match(io_value)
        if found:
            # avoid probs if run again - don't add if already present
            needed = '146-0{}'.format(found.group(1))
            replacements[found.group(1)] = '0{}'.format(found.group(1))
            if needed not in existing_values:
                needed_i = Identifier(
                    use='secondary', system=IRONMAN_system, _value=needed)
            else:
                needed_i = Identifier.query.filter(
                    Identifier.system == IRONMAN_system).filter(
                    Identifier._value == needed).one()

            # add a 3 digit identifier and link with same org
            oi = OrganizationIdentifier.query.filter(
                OrganizationIdentifier.identifier_id == io_id).one()
            needed_oi = OrganizationIdentifier.query.filter(
                OrganizationIdentifier.organization_id ==
                oi.organization_id).filter(
                OrganizationIdentifier.identifier == needed_i).first()
            if not needed_oi:
                needed_i = session.merge(needed_i)
                needed_oi = OrganizationIdentifier(
                    organization_id=oi.organization_id,
                    identifier=needed_i)
                session.add(needed_oi)

    # All IRONMAN users with a 2 digit ID referencing one of the replaced
    # values needs a 3 digit version

    ironman_study_ids = Identifier.query.filter(
        Identifier.system == TRUENTH_EXTERNAL_STUDY_SYSTEM).filter(
        Identifier._value.like('170-%')).with_entities(
        Identifier.id, Identifier._value)

    for iid, ival in ironman_study_ids:
        found = study_pattern.match(ival)
        if found:
            org_segment = found.group(1)
            patient_segment = found.group(2)

            # only add if also one of the new org ids
            if org_segment not in replacements:
                continue

            needed = '170-{}-{}'.format(
                replacements[org_segment], patient_segment)

            # add a 3 digit identifier and link with same user(s),
            # if not already present
            uis = UserIdentifier.query.filter(
                UserIdentifier.identifier_id == iid)
            needed_i = Identifier.query.filter(
                Identifier.system == TRUENTH_EXTERNAL_STUDY_SYSTEM).filter(
                Identifier._value == needed).first()
            if not needed_i:
                needed_i = Identifier(
                    use='secondary', system=TRUENTH_EXTERNAL_STUDY_SYSTEM,
                    _value=needed)
            for ui in uis:
                needed_ui = UserIdentifier.query.filter(
                    UserIdentifier.user_id == ui.user_id).filter(
                    UserIdentifier.identifier == needed_i).first()
                if not needed_ui:
                    needed_ui = UserIdentifier(
                        user_id=ui.user_id, identifier=needed_i)
                    session.add(needed_ui)

    session.commit()


def downgrade():
    pass
