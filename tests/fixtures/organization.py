import pytest
from flask_webtest import SessionScope

from portal.database import db
from portal.models.organization import (
    Organization,
    OrganizationResearchProtocol,
)


@pytest.fixture
def initialized_with_org(initialized_with_research_protocol):
    org = Organization(name="test_org")
    # Add the intermediary table type to include the
    # retired_as_of value.  Magic of association proxy, bringing
    # one to life commits, and trying to add directly will fail
    orp = OrganizationResearchProtocol(
        research_protocol=initialized_with_research_protocol,
        organization=org,
        retired_as_of=None)
    with SessionScope(db):
        db.session.add(org)
        db.session.add(orp)
        db.session.commit()
    return db.session.merge(org)
