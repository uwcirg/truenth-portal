"""Unit test module for ResearchProtocol logic"""
from datetime import datetime
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.organization import Organization
from portal.models.research_protocol import ResearchProtocol
from portal.system_uri import TRUENTH_RP_EXTENSION


def test_rp_from_json(initialized_with_research_study):
    # test from_fhir for new RP
    data = {"name": "test_rp", "research_study_id": 0}
    rp = ResearchProtocol.from_json(data)
    with SessionScope(db):
        db.session.add(rp)
        db.session.commit()
    rp = db.session.merge(rp)

    assert rp.id
    assert rp.created_at
    assert rp.name == "test_rp"
    assert rp.research_study_id == 0


def test_rp_as_json(initialized_with_research_protocol):
    rp_json = initialized_with_research_protocol.as_json()
    assert rp_json['name'] == 'test_rp'
    assert rp_json['created_at']
    assert rp_json['display_name'] == 'Test Rp'
    assert rp_json['research_study_id'] == 0


def test_org_rp_reference(initialized_with_research_protocol):
    rp = initialized_with_research_protocol
    org_data = {"name": "test_org",
                "extension": [
                    {"url": TRUENTH_RP_EXTENSION,
                     "research_protocols": [{'name': rp.name}]}
                ]}

    org = Organization.from_fhir(org_data)
    assert len(org.research_protocols) == 1
    assert org.research_protocols[0].id == rp.id


def test_rp_inheritance(initialized_with_research_protocol):
    rp = initialized_with_research_protocol
    parent = Organization(name='parent', id=101)
    parent.research_protocols.append(rp)
    child = Organization(name='child', partOf_id=101)
    with SessionScope(db):
        db.session.add(parent)
        db.session.add(child)
        db.session.commit()
    parent, child, rp = map(db.session.merge, (parent, child, rp))

    assert len(parent.research_protocols) == 1
    assert parent.research_protocols[0].id == rp.id
    assert parent.research_protocols[0].research_study_id == 0
    assert len(child.research_protocols) == 0
    assert (child.research_protocol(
        research_study_id=0, as_of_date=datetime.utcnow()).id == rp.id)
