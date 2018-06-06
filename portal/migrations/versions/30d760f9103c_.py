import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import sessionmaker

from portal.models.fhir import QuestionnaireResponse
from portal.models.intervention import Intervention
from portal.models.intervention_strategies import observation_check
from portal.models.organization import OrgTree
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import QuestionnaireBank

"""empty message

Revision ID: 30d760f9103c
Revises: 6abf0247a320
Create Date: 2017-09-06 13:13:32.576485

"""

# revision identifiers, used by Alembic.
revision = '30d760f9103c'
down_revision = '6abf0247a320'

Session = sessionmaker()


def qbs_for_user(user, session):
    users_top_orgs = set()
    for org in (o for o in user.organizations if o.id):
        users_top_orgs.add(OrgTree().find(org.id).top_level())

    results = [] if not users_top_orgs else (
        session.query(QuestionnaireBank).filter(
            QuestionnaireBank.organization_id.in_(users_top_orgs)).all())

    intervention_associated_qbs = session.query(QuestionnaireBank).filter(
        QuestionnaireBank.intervention_id.isnot(None))
    for qb in intervention_associated_qbs:
        intervention = session.query(Intervention).get(qb.intervention_id)
        display_details = intervention.display_for_user(user)
        if display_details.access:
            chec_func = observation_check("biopsy", 'true')
            if chec_func(intervention=intervention, user=user):
                results.append(qb)
    return results


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('questionnaire_responses', sa.Column('questionnaire_bank_id',
                                                       sa.Integer(), nullable=True))
    op.create_foreign_key('qnr_qb_id_fkey', 'questionnaire_responses',
                          'questionnaire_banks', ['questionnaire_bank_id'], ['id'])
    # ### end Alembic commands ###

    bind = op.get_bind()
    session = Session(bind=bind)

    #for qnr in session.query(QuestionnaireResponse):
    #    if ("questionnaire" in qnr.document) and qnr.subject:
    #        qn_ref = qnr.document.get("questionnaire").get("reference")
    #        qn_name = qn_ref.split("/")[-1] if qn_ref else None
    #        qn = session.query(Questionnaire).filter_by(name=qn_name).first()
    #        for qb in qbs_for_user(qnr.subject, session):
    #            for qbq in qb.questionnaires:
    #                if qbq.questionnaire == qn:
    #                    qnr.questionnaire_bank = qb

    session.commit()


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('qnr_qb_id_fkey', 'questionnaire_responses', type_='foreignkey')
    op.drop_column('questionnaire_responses', 'questionnaire_bank_id')
    # ### end Alembic commands ###
