"""Add 3 digit version of all 2 digit IRONMAN identifiers

Revision ID: 265e7dc4c1a5
Revises: 2e1421ac841a
Create Date: 2019-04-23 11:29:22.633160

"""
import re

from portal.database import db
from portal.models.identifier import Identifier
from portal.models.organization import OrganizationIdentifier
from portal.models.user import UserIdentifier
from portal.system_uri import TRUENTH_EXTERNAL_STUDY_SYSTEM

# revision identifiers, used by Alembic.
revision = '265e7dc4c1a5'
down_revision = '2e1421ac841a'

org_pattern = re.compile(r'^146-(\d\d)$')
study_pattern = re.compile(r'^170-(\d\d)-(\d\d\d)$')


def upgrade():
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
            if needed in existing_values:
                continue

            replacements[found.group(1)] = '0{}'.format(found.group(1))

            # add a 3 digit identifier and link with same org
            oi = OrganizationIdentifier.query.filter(
                OrganizationIdentifier.identifier_id == io_id).one()
            needed_i = Identifier(
                use='secondary', system=IRONMAN_system, _value=needed)
            needed_oi = OrganizationIdentifier(
                organization_id=oi.organization_id, identifier=needed_i)
            db.session.add(needed_oi)

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

            # add a 3 digit identifier and link with same user(s)
            uis = UserIdentifier.query.filter(
                UserIdentifier.identifier_id == iid)
            needed_i = Identifier(
                use='secondary', system=TRUENTH_EXTERNAL_STUDY_SYSTEM,
                _value=needed)
            for ui in uis:
                needed_ui = UserIdentifier(
                    user_id=ui.user_id, identifier=needed_i)
                db.session.add(needed_ui)

    db.session.commit()


def downgrade():
    pass
