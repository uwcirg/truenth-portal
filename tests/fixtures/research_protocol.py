import pytest
from flask_webtest import SessionScope

from portal.database import db
from portal.models.research_protocol import ResearchProtocol


@pytest.fixture
def initialized_with_research_protocol(initialized_with_research_study):
    rp = ResearchProtocol(name="test_rp", research_study_id=0)
    with SessionScope(db):
        db.session.add(rp)
        db.session.commit()
    return db.session.merge(rp)


@pytest.fixture
def initialized_with_ss_protocol(
        initialized_with_research_protocol,
        initialized_with_research_substudy):
    rp = ResearchProtocol(
        name="substudy_rp",
        research_study_id=initialized_with_research_substudy.id)
    with SessionScope(db):
        db.session.add(rp)
        db.session.commit()
    return db.session.merge(rp)
