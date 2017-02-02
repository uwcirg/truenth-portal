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
import re
from sqlalchemy.orm import sessionmaker
from portal.models.audit import Audit

Session = sessionmaker()

def extract_context(comment):
    contexts = [
        ('login',['login','logout']),
        ('assessment',['patient report','questionnaireresponse']),
        ('authentication',['assuming identity', 'service',
            'inadequate permission','identity challenge',
            'access token']),
        ('intervention',['intervention', r'client .* assuming role',
            r'client .* releasing role',r'updated .* using']),
        ('account',['register','merging','account','marking deleted',
            'purging','registration']),
        ('user',['time of death','deceased','demographics']),
        ('organization',['organization',r'adding .* to']),
        ('consent',['consent']),
        ('observation',['observation',r'set codeableconcept .* on user']),
        ('group',['group']),
        ('procedure',['procedure']),
        ('relationship',['relationship']),
        ('role',['role']),
        ('tou',['tou']),
        ('other',['remote','test'])
    ]
    for ct in contexts:
        for searchterm in ct[1]:
            if re.search(searchterm, comment):
                return ct[0]
    return 'other'

def upgrade():
    op.add_column('audit', sa.Column('subject_id', sa.Integer()))
    op.create_foreign_key('audit_subject_id_fkey', 'audit', 'users', ['subject_id'], ['id'])

    op.add_column('audit', sa.Column('context', sa.Text(), nullable=True))

    # copying user_id to subject_id for existing audit rows
    bind = op.get_bind()
    session = Session(bind=bind)

    for audit in session.query(Audit):
        # use user_id as subject_id by default
        audit.subject_id = audit.user_id

        # use 'other' as context by default
        audit.context = "other"

        if audit.comment:
            # if comment references changed user, use that as subject_id
            audit_comment_list = audit.comment.split()
            if "user" in audit_comment_list:
                subj_id = audit_comment_list[audit_comment_list.index("user") + 1]
                if subj_id.isdigit():
                    audit.subject_id = int(subj_id)

            # if possible, use context extracted from comment
            audit.context = extract_context(audit.comment.lower())

    session.commit()

    op.alter_column('audit', 'subject_id', nullable=False)
    op.alter_column('audit', 'context', nullable=False)


def downgrade():
    op.drop_column('audit', 'context')

    op.drop_constraint('audit_subject_id_fkey', 'audit', type_='foreignkey')
    op.drop_column('audit', 'subject_id')
