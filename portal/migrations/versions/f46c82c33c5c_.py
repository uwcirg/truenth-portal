"""Multiple clinicians per patient

Revision ID: f46c82c33c5c
Revises: 64fef97d19ec
Create Date: 2021-02-22 14:05:07.958270

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision = 'f46c82c33c5c'
down_revision = '64fef97d19ec'


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    op.create_table('user_clinicians',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('clinician_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['clinician_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )

    # migrate all existing clinicians from user.clinician_id
    # to user_clinician rows
    results = session.execute(
        "SELECT id, clinician_id FROM users WHERE clinician_id IS NOT NULL")
    insert = text(
        "INSERT INTO user_clinicians (patient_id, clinician_id) "
        "VALUES (:patient_id, :clinician_id)")

    for patient_id, clinician_id in results:
        session.execute(
            insert,
            {'patient_id': patient_id, 'clinician_id': clinician_id})
    session.commit()

    op.drop_index('ix_users_clinician_id', table_name='users')
    op.drop_constraint('users_clinician_id_fkey', 'users', type_='foreignkey')
    op.drop_column('users', 'clinician_id')


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    op.add_column('users', sa.Column(
        'clinician_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(
        'users_clinician_id_fkey', 'users', 'users', ['clinician_id'], ['id'])
    op.create_index(
        'ix_users_clinician_id', 'users', ['clinician_id'], unique=False)

    results = session.execute(
        "SELECT patient_id, clinician_id FROM user_clinicians")
    update = text(
        "UPDATE users SET clinician_id=:clinician_id WHERE id=:patient_id")

    for patient_id, clinician_id in results:
        session.execute(
            update, {'patient_id': patient_id, 'clinician_id': clinician_id})
    session.commit()

    op.drop_table('user_clinicians')
