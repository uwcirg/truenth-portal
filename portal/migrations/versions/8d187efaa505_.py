import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import sessionmaker

from portal.models.organization import Organization
from portal.models.research_protocol import ResearchProtocol

"""empty message

Revision ID: 8d187efaa505
Revises: dc58763db4a8
Create Date: 2017-11-06 17:30:01.086866

"""

# revision identifiers, used by Alembic.
revision = '8d187efaa505'
down_revision = 'dc58763db4a8'

Session = sessionmaker()


def migrate_to_rp(org_id, rp_name):
    bind = op.get_bind()
    session = Session(bind=bind)

    org = session.query(Organization).get(org_id)
    if org:
        rp = ResearchProtocol(name=rp_name)
        session.add(rp)
        session.commit()
        rp = session.merge(rp)
        rp_id = rp.id

        session.execute('UPDATE organizations '
                        'SET research_protocol_id = {} '
                        'WHERE id = {}'.format(rp_id, org_id))

        session.execute('UPDATE questionnaire_banks '
                        'SET research_protocol_id = {} '
                        'WHERE organization_id = {}'.format(rp_id, org_id))


def migrate_from_rp(org_id, rp_name):
    bind = op.get_bind()
    session = Session(bind=bind)

    org = session.query(Organization).get(org_id)
    rp = session.query(ResearchProtocol).filter_by(name=rp_name).first()
    if org and rp:
        session.execute('UPDATE questionnaire_banks '
                        'SET organization_id = {} WHERE '
                        'research_protocol_id = {}'.format(org_id, rp.id))


def upgrade():
    op.create_table('research_protocols',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.Text(), nullable=False),
                    sa.Column('created_at', sa.DateTime(), nullable=False),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('name')
                    )
    op.add_column(u'organizations', sa.Column('research_protocol_id',
                                              sa.Integer(), nullable=True))
    op.create_foreign_key('organizations_rp_id_fkey', 'organizations',
                          'research_protocols',
                          ['research_protocol_id'], ['id'])

    op.add_column('questionnaire_banks',
                  sa.Column('research_protocol_id', sa.Integer(),
                            nullable=True))
    op.create_foreign_key('questionnaire_banks_rp_id_fkey',
                          'questionnaire_banks', 'research_protocols',
                          ['research_protocol_id'], ['id'])
    op.drop_constraint(u'questionnaire_banks_organization_id_fkey',
                       'questionnaire_banks', type_='foreignkey')
    op.drop_constraint('ck_qb_intv_org_mutual_exclusion',
                       'questionnaire_banks')

    migrate_to_rp(10000, 'TNGR v1')
    migrate_to_rp(20000, 'IRONMAN v2')
    op.create_check_constraint(
        'ck_qb_intv_rp_mutual_exclusion',
        'questionnaire_banks',
        'NOT(research_protocol_id IS NULL AND intervention_id IS NULL) '
        'AND NOT(research_protocol_id IS NOT NULL AND '
        'intervention_id IS NOT NULL)')
    op.drop_column('questionnaire_banks', 'organization_id')


def downgrade():
    op.add_column('questionnaire_banks',
                  sa.Column('organization_id', sa.INTEGER(),
                            autoincrement=False, nullable=True))
    op.drop_constraint('questionnaire_banks_rp_id_fkey',
                       'questionnaire_banks', type_='foreignkey')
    op.create_foreign_key(u'questionnaire_banks_organization_id_fkey',
                          'questionnaire_banks', 'organizations',
                          ['organization_id'], ['id'])
    op.drop_constraint('organizations_rp_id_fkey', 'organizations',
                       type_='foreignkey')
    op.drop_constraint('ck_qb_intv_rp_mutual_exclusion',
                       'questionnaire_banks')

    migrate_from_rp(10000, 'TNGR v1')
    migrate_from_rp(20000, 'IRONMAN v2')
    op.drop_column('questionnaire_banks', 'research_protocol_id')
    op.create_check_constraint(
        'ck_qb_intv_org_mutual_exclusion',
        'questionnaire_banks',
        'NOT(organization_id IS NULL AND intervention_id IS NULL) '
        'AND NOT(organization_id IS NOT NULL AND intervention_id IS NOT NULL)')
    op.drop_column(u'organizations', 'research_protocol_id')
    op.drop_table('research_protocols')
