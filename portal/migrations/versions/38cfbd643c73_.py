"""empty message

Revision ID: 38cfbd643c73
Revises: 5d7a1030065e
Create Date: 2017-06-07 15:43:36.972833

"""

# revision identifiers, used by Alembic.
revision = '38cfbd643c73'
down_revision = '5d7a1030065e'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.models.audit import Audit
from portal.models.role import Role
from portal.models.user import User, UserRoles


Session = sessionmaker()


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    op.drop_constraint(u'observations_audit_id_fkey', 'observations', type_='foreignkey')
    op.drop_column('observations', 'audit_id')
    op.add_column('user_observations', sa.Column('audit_id', sa.Integer(), nullable=True))
    op.create_foreign_key(u'user_observations_audit_id_fkey', 'user_observations',
                          'audit', ['audit_id'], ['id'])

    # create new audits for UserObservations
    for uo_id, user_id in session.execute('SELECT id, user_id FROM user_observations'):
        aud = Audit(user_id=user_id, subject_id=user_id,
                    comment="entry predates audit records for user observations")
        session.add(aud)
        session.commit()
        aud = session.merge(aud)
        session.execute('UPDATE user_observations SET audit_id = {} '
                        'WHERE id = {}'.format(aud.id, uo_id))

    op.alter_column('user_observations', 'audit_id', nullable=False)

    # delete any audits created in any past downgrades
    session.execute("DELETE from audit "
                    "WHERE comment = 'entry replaces audit records for user observations'")


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    op.drop_constraint(u'user_observations_audit_id_fkey', 'user_observations', type_='foreignkey')
    op.drop_column('user_observations', 'audit_id')
    op.add_column('observations',
                  sa.Column('audit_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(u'observations_audit_id_fkey', 'observations',
                          'audit', ['audit_id'], ['id'])

    # create new audits for Observations
    admin = User.query.filter_by(email='bob25mary@gmail.com').first()
    admin = admin or User.query.join(
            UserRoles).join(Role).filter(sa.and_(Role.id == UserRoles.role_id,
                                                 UserRoles.user_id == User.id,
                                                 Role.name == 'admin')).first()
    admin_id = admin.id

    for obs_id in session.execute('SELECT id FROM observations where audit_id IS NULL'):
        aud = Audit(user_id=admin_id, subject_id=admin_id,
                    comment="entry replaces audit records for user observations")
        session.add(aud)
        session.commit()
        aud = session.merge(aud)
        session.execute('UPDATE observations SET audit_id = {} '
                        'WHERE id = {}'.format(aud.id, obs_id[0]))

    op.alter_column('observations', 'audit_id', nullable=False)

    # delete any audits created in the upgrade
    session.execute("DELETE from audit "
                    "WHERE comment = 'entry predates audit records for user observations'")
