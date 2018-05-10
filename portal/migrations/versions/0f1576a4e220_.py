from alembic import op
from sqlalchemy.orm import sessionmaker

"""remove WRITE_ONLY from service accounts

Revision ID: 0f1576a4e220
Revises: ed70c144ae46
Create Date: 2018-05-09 14:40:13.818624

"""

# revision identifiers, used by Alembic.
revision = '0f1576a4e220'
down_revision = 'ed70c144ae46'

Session = sessionmaker()


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    session.execute("""DELETE FROM user_roles ur USING roles r
        WHERE r.id = ur.role_id AND ur.user_id IN 
        (SELECT user_id FROM user_roles JOIN roles ON roles.id = role_id
         WHERE roles.name = 'service')
        AND r.name = 'write_only'""")


def downgrade():
    # no value in restoring that state.
    pass
    # ### end Alembic commands ###
