"""empty message

Revision ID: b92dc277c384
Revises: 5d1daa0f3a14
Create Date: 2017-05-10 10:34:12.617168

"""

# revision identifiers, used by Alembic.
revision = 'b92dc277c384'
down_revision = '5d1daa0f3a14'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from portal.models.telecom import ContactPoint

Session = sessionmaker()


def upgrade():
    # create contact_points table
    op.create_table(
        'contact_points',
        sa.Column(
            'id',
            sa.Integer(),
            nullable=False),
        sa.Column(
            'cp_sys',
            postgresql.ENUM(
                'phone',
                'fax',
                'email',
                'pager',
                'url',
                'sms',
                'other',
                name='cp_sys'),
            nullable=False),
        sa.Column(
            'cp_use',
            postgresql.ENUM(
                'home',
                'work',
                'temp',
                'old',
                'mobile',
                name='cp_use'),
            nullable=True),
        sa.Column(
            'value',
            sa.Text(),
            nullable=True),
        sa.Column(
            'rank',
            sa.Integer(),
            nullable=True),
        sa.PrimaryKeyConstraint('id'))

    # add new phone_id columns
    op.add_column(u'users', sa.Column(
        'alt_phone_id', sa.Integer(), nullable=True))
    op.add_column(u'users', sa.Column('phone_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'user_alt_phone_contact_point',
        'users',
        'contact_points',
        ['alt_phone_id'],
        ['id'],
        ondelete='cascade')
    op.create_foreign_key(
        'user_phone_contact_point',
        'users',
        'contact_points',
        ['phone_id'],
        ['id'],
        ondelete='cascade')

    op.add_column(u'organizations', sa.Column(
        'phone_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'org_phone_contact_point',
        'organizations',
        'contact_points',
        ['phone_id'],
        ['id'],
        ondelete='cascade')

    # migrate data from old phone columns to new contact_point objects
    bind = op.get_bind()
    session = Session(bind=bind)

    for user_id, phone in session.execute(
            "SELECT id, phone FROM users where phone != ''"):
        cp = ContactPoint(system='phone', use='mobile', value=phone)
        session.add(cp)
        session.commit()
        cp = session.merge(cp)
        session.execute(
            'UPDATE users SET phone_id = {} where id = {}'.format(
                cp.id, user_id))

    for org_id, phone in session.execute(
            "SELECT id, phone FROM organizations where phone != ''"):
        cp = ContactPoint(system='phone', use='work', value=phone)
        session.add(cp)
        session.commit()
        cp = session.merge(cp)
        session.execute(
            'UPDATE organizations SET phone_id = {} where id = {}'.format(
                cp.id, org_id))

    # drop old phone columns
    op.drop_column(u'users', 'phone')
    op.drop_column(u'organizations', 'phone')


def downgrade():
    # recreate old phone columns
    op.add_column(u'users', sa.Column('phone', sa.VARCHAR(
        length=40), autoincrement=False, nullable=True))
    op.add_column(u'organizations', sa.Column(
        'phone', sa.VARCHAR(length=40), autoincrement=False, nullable=True))

    # migrate data from new contact_point objects to old phone columns
    bind = op.get_bind()
    session = Session(bind=bind)

    for user_id, phone_id in session.execute(
            'SELECT id, phone_id FROM users WHERE phone_id IS NOT NULL'):
        phone = session.execute(
            'SELECT value FROM contact_points WHERE id = {}'.format(phone_id)).fetchone()[0]
        session.execute(
            "UPDATE users SET phone = '{}' where id = {}".format(
                phone, user_id))

    for org_id, phone_id in session.execute(
            'SELECT id, phone_id FROM organizations WHERE phone_id IS NOT NULL'):
        phone = session.execute(
            'SELECT value FROM contact_points WHERE id = {}'.format(phone_id)).fetchone()[0]
        session.execute(
            "UPDATE organizations SET phone = '{}' where id = {}".format(
                phone, org_id))

    # remove contact_points table and phone_id columns
    op.drop_constraint('user_phone_contact_point', 'users', type_='foreignkey')
    op.drop_constraint('user_alt_phone_contact_point',
                       'users', type_='foreignkey')
    op.drop_column(u'users', 'phone_id')
    op.drop_column(u'users', 'alt_phone_id')
    op.drop_constraint('org_phone_contact_point',
                       'organizations', type_='foreignkey')
    op.drop_column(u'organizations', 'phone_id')
    op.drop_table('contact_points')

    session.execute("DROP TYPE cp_sys")
    session.execute("DROP TYPE cp_use")
    ### end Alembic commands ###
