"""empty message

Revision ID: 0ac4b88c909f
Revises: feb22883a500
Create Date: 2017-04-12 11:40:48.930401

"""

# revision identifiers, used by Alembic.
revision = '0ac4b88c909f'
down_revision = 'feb22883a500'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    # strip the invite prefix from no_email users
    conn = op.get_bind()
    result = conn.execute(text(
        """SELECT id, email FROM users WHERE email like '__invite____no_email__%'"""))
    results = result.fetchall()
    for r in results:
        conn.execute(text("""UPDATE users SET email=:improved WHERE id=:id"""),
                     improved=r[1][len('__invite__'):], id=r[0])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
