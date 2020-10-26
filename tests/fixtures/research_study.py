from flask_webtest import SessionScope
from pytest import fixture

from portal.database import db
from portal.models.research_study import (
    ResearchStudy,
    add_static_research_studies,
)


@fixture
def initialized_with_research_study(initialized_db):
    add_static_research_studies()
    db.session.commit()


@fixture
def initialized_with_research_substudy(initialized_with_research_study):
    ss_rs = ResearchStudy(id=1, title='substudy_rs')
    with SessionScope(db):
        db.session.add(ss_rs)
        db.session.commit()
    return db.session.merge(ss_rs)
