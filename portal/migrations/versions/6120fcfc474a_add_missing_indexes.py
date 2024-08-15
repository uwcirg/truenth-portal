"""add missing indexes

Revision ID: 6120fcfc474a
Revises: cf586ed4f043
Create Date: 2024-08-06 17:49:02.447759

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6120fcfc474a'
down_revision = 'cf586ed4f043'


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_audit_context'), 'audit', ['context'], unique=False)
    op.create_index(op.f('ix_audit_subject_id'), 'audit', ['subject_id'], unique=False)
    op.create_index(op.f('ix_audit_user_id'), 'audit', ['user_id'], unique=False)
    op.create_index(op.f('ix_communications_communication_request_id'), 'communications', ['communication_request_id'], unique=False)
    op.create_index(op.f('ix_communications_status'), 'communications', ['status'], unique=False)
    op.create_index(op.f('ix_communications_user_id'), 'communications', ['user_id'], unique=False)
    op.create_index(op.f('ix_email_messages_recipients'), 'email_messages', ['recipients'], unique=False)
    op.create_index(op.f('ix_encounter_codings_encounter_id'), 'encounter_codings', ['encounter_id'], unique=False)
    op.create_index(op.f('ix_encounters_status'), 'encounters', ['status'], unique=False)
    op.create_index(op.f('ix_encounters_user_id'), 'encounters', ['user_id'], unique=False)
    op.create_index(op.f('ix_questionnaire_responses_encounter_id'), 'questionnaire_responses', ['encounter_id'], unique=False)
    op.create_index(op.f('ix_questionnaire_responses_subject_id'), 'questionnaire_responses', ['subject_id'], unique=False)
    op.create_index(op.f('ix_tou_audit_id'), 'tou', ['audit_id'], unique=False)
    op.create_index(op.f('ix_user_observations_audit_id'), 'user_observations', ['audit_id'], unique=False)
    op.create_index(op.f('ix_user_observations_observation_id'), 'user_observations', ['observation_id'], unique=False)
    op.create_index(op.f('ix_user_observations_user_id'), 'user_observations', ['user_id'], unique=False)

# The following are added by hand, as the syntax for JSONB indexes isn't available in active version
    op.execute("CREATE INDEX IF NOT EXISTS idx_qnr_identifier_val2 ON questionnaire_responses(((document->'identifier')->'value'))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_qnr_identifier_sys2 ON questionnaire_responses(((document->'identifier')->'system'))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_qnr_authored ON questionnaire_responses((document->'authored'))")

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_tou_audit_id'), table_name='tou')
    op.drop_index(op.f('ix_questionnaire_responses_subject_id'), table_name='questionnaire_responses')
    op.drop_index(op.f('ix_questionnaire_responses_encounter_id'), table_name='questionnaire_responses')
    op.drop_index(op.f('ix_encounters_user_id'), table_name='encounters')
    op.drop_index(op.f('ix_encounters_status'), table_name='encounters')
    op.drop_index(op.f('ix_encounter_codings_encounter_id'), table_name='encounter_codings')
    op.drop_index(op.f('ix_email_messages_recipients'), table_name='email_messages')
    op.drop_index(op.f('ix_communications_user_id'), table_name='communications')
    op.drop_index(op.f('ix_communications_status'), table_name='communications')
    op.drop_index(op.f('ix_communications_communication_request_id'), table_name='communications')
    op.drop_index(op.f('ix_audit_user_id'), table_name='audit')
    op.drop_index(op.f('ix_audit_subject_id'), table_name='audit')
    op.drop_index(op.f('ix_audit_context'), table_name='audit')
    op.drop_index(op.f('ix_user_observations_audit_id'), table_name='user_observations')
    op.drop_index(op.f('ix_user_observations_observation_id'), table_name='user_observations')
    op.drop_index(op.f('ix_user_observations_user_id'), table_name='user_observations')

    # and the ones added by hand
    op.drop_index(op.f('idx_qnr_identifier_val2'), table_name='questionnaire_responses')
    op.drop_index(op.f('idx_qnr_identifier_sys2'), table_name='questionnaire_responses')
    op.drop_index(op.f('idx_qnr_authored'), table_name='questionnaire_responses')
    # ### end Alembic commands ###