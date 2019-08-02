"""Unit test module for ResearchProtocol logic"""

from datetime import datetime

from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.organization import Organization
from portal.models.research_protocol import ResearchProtocol
from portal.system_uri import TRUENTH_RP_EXTENSION
from tests import TestCase


class TestResearchProtocol(TestCase):
    """Research Protocol tests"""

    def test_rp_from_json(self):
        # test from_fhir for new RP
        data = {"name": "test_rp"}
        rp = ResearchProtocol.from_json(data)
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)

        assert rp.id
        assert rp.created_at

    def test_rp_as_json(self):
        rp = ResearchProtocol(name="test_rp")
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)

        rp_json = rp.as_json()
        assert rp_json['name'] == 'test_rp'
        assert rp_json['created_at']
        assert rp_json['display_name'] == 'Test Rp'

    def test_org_rp_reference(self):
        rp = ResearchProtocol(name="test_rp")
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)

        org_data = {"name": "test_org",
                    "extension": [
                        {"url": TRUENTH_RP_EXTENSION,
                         "research_protocols": [{'name': "test_rp"}]}
                    ]}

        org = Organization.from_fhir(org_data)
        assert len(org.research_protocols) == 1
        assert org.research_protocols[0].id == rp.id

    def test_rp_inheritance(self):
        rp = ResearchProtocol(name="test_rp")
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)

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
        assert len(child.research_protocols) == 0
        assert (child.research_protocol(as_of_date=datetime.utcnow()).id
                == rp.id)
