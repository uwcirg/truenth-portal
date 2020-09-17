from pytest import fixture
from portal.database import db
from portal.models.research_study import add_static_research_studies


@fixture
def initialized_with_research_study(initialized_db):
    add_static_research_studies()
    db.session.commit()


