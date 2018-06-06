"""empty message

Revision ID: b1d13b4b175a
Revises: 7793ca45b7f9
Create Date: 2016-12-14 12:55:17.942109

"""

# revision identifiers, used by Alembic.
revision = 'b1d13b4b175a'
down_revision = '533fc09a4d32'

import sqlalchemy as sa
from alembic import op


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_documents',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('document_type', sa.Text(), nullable=False),
                    sa.Column('filename', sa.Text(), nullable=False),
                    sa.Column('filetype', sa.Text(), nullable=False),
                    sa.Column('uuid', sa.Text(), nullable=False),
                    sa.Column('uploaded_at', sa.DateTime(), nullable=False),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('user_documents')
    ### end Alembic commands ###
