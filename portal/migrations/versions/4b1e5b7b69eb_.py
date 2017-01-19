"""empty message

Revision ID: 4b1e5b7b69eb
Revises: 13d1c714823a
Create Date: 2017-01-19 12:36:55.339537

"""

# revision identifiers, used by Alembic.
revision = '4b1e5b7b69eb'
down_revision = '13d1c714823a'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from portal.models.audit import Audit

Session = sessionmaker()

def upgrade():
    op.add_column('audit', sa.Column('subject_id', sa.Integer()))
    op.create_foreign_key('audit_subject_id_fkey', 'audit', 'users', ['subject_id'], ['id'])

    # copying user_id to subject_id for existing audit rows
    bind = op.get_bind()
    session = Session(bind=bind)

    for audit in session.query(Audit):
        #import pdb; pdb.set_trace()
        # use user_id as subject_id by default
        audit.subject_id = audit.user_id

        # if comment references changed user, use that as subject_id
        if audit.comment and ("user" in audit.comment):
            audit_comment_list = audit.comment.split()
            subj_id = audit_comment_list[audit_comment_list.index("user") + 1]
            if subj_id.isdigit():
                audit.subject_id = int(subj_id)

    session.commit()

    op.alter_column('audit', 'subject_id', nullable=False)


def downgrade():
    op.drop_constraint('audit_subject_id_fkey', 'audit', type_='foreignkey')
    op.drop_column('audit', 'subject_id')
