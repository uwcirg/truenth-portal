"""remove non english rows from report data (IRONN-264)

Revision ID: 4f5daa2b48db
Revises: 967a074a0404
Create Date: 2024-11-25 13:48:01.321510

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '4f5daa2b48db'
down_revision = '967a074a0404'


def upgrade():
    connection = op.get_bind()
    connection.execute("DELETE FROM research_data WHERE NOT (data->>'timepoint' ~ '^(Baseline|Month)');")
    # next run of `cache_research_data()` will pick up those just deleted.


def downgrade():
    # no point in bringing those back
    pass
