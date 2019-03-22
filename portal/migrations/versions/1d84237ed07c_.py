"""Move comma delimited ints to proper list in table_preferences

Revision ID: 1d84237ed07c
Revises: 69af4bd9ac9a
Create Date: 2019-03-12 14:16:02.704403

"""
import copy
from portal.database import db
from portal.models.table_preference import TablePreference

# revision identifiers, used by Alembic.
revision = '1d84237ed07c'
down_revision = '69af4bd9ac9a'


def patch_filters(filters):
    """return correct datatype in filters['orgs_filter_control'] """
    results = copy.deepcopy(filters)
    results['orgs_filter_control'] = list()
    for oid in filters['orgs_filter_control'].split(','):
        if oid:
            results['orgs_filter_control'].append(int(oid))
    return results


def unpatch_filters(filters):
    """return older comma delimited str in filters['orgs_filter_control'] """
    results = copy.deepcopy(filters)
    oids = ','.join([str(x) for x in filters['orgs_filter_control']])
    results['orgs_filter_control'] = oids

    return results


def upgrade():
    query = TablePreference.query.filter(
        TablePreference.table_name == 'patientList')
    for pref in query:
        if 'orgs_filter_control' in pref.filters:
            pref.filters = patch_filters(pref.filters)

    db.session.commit()


def downgrade():
    query = TablePreference.query.filter(
        TablePreference.table_name == 'patientList')
    for pref in query:
        if 'orgs_filter_control' in pref.filters:
            pref.filters = unpatch_filters(pref.filters)

    db.session.commit()
