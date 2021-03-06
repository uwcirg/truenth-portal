"""ResearchProtocol becomes ResearchStudy aware

Revision ID: 30f20e54eb5c
Revises: 1977c23a53c8
Create Date: 2020-08-27 13:33:08.560635

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '30f20e54eb5c'
down_revision = '1977c23a53c8'


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        'research_protocols',
        sa.Column('research_study_id', sa.Integer()))
    con = op.get_bind()
    result = con.execute('SELECT id FROM research_studies WHERE id = 0')
    if not result.rowcount:
        op.execute(
            "INSERT INTO research_studies (id, title) VALUES"
            " (0, 'placeholder')")

    op.execute('UPDATE research_protocols SET research_study_id = 0')
    op.alter_column('research_protocols', 'research_study_id', nullable=False)

    op.create_index(
        op.f('ix_research_protocols_research_study_id'),
        'research_protocols',
        ['research_study_id'],
        unique=False)
    op.create_foreign_key(
        None,
        'research_protocols',
        'research_studies',
        ['research_study_id'],
        ['id'],
        ondelete='cascade')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        op.f('research_protocols_research_study_id_fkey'),
        'research_protocols',
        type_='foreignkey')
    op.drop_index(
        op.f('ix_research_protocols_research_study_id'),
        table_name='research_protocols')
    op.drop_column('research_protocols', 'research_study_id')
    # ### end Alembic commands ###
