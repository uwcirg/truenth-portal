"""Unit test module for ResearchProtocol logic"""
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

        self.assertTrue(rp.id)
        self.assertTrue(rp.created_at)

        # test from_fhir for existing RP does not create new
        rp2 = ResearchProtocol.from_json(data)
        self.assertEquals(ResearchProtocol.query.count(), 1)
        self.assertEquals(rp2.id, rp.id)
        self.assertEquals(rp2.created_at, rp.created_at)

    def test_rp_as_json(self):
        rp = ResearchProtocol(name="test_rp")
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)

        rp_json = rp.as_json()
        self.assertEquals(rp_json['name'], 'test_rp')
        self.assertTrue(rp_json['created_at'])

    def test_org_rp_reference(self):
        rp = ResearchProtocol(name="test_rp")
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)

        org_data = {"name": "test_org",
                    "extension": [
                    {"url": TRUENTH_RP_EXTENSION,
                     "research_protocol": "test_rp"}
                    ]}

        org = Organization.from_fhir(org_data)
        self.assertEquals(org.research_protocol_id, rp.id)
