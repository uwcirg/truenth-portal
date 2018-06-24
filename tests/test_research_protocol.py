"""Unit test module for ResearchProtocol logic"""
from datetime import datetime
import sys

from flask_webtest import SessionScope
import pytest

from portal.extensions import db
from portal.models.organization import Organization
from portal.models.research_protocol import ResearchProtocol
from portal.system_uri import TRUENTH_RP_EXTENSION
from tests import TestCase

if sys.version_info.major > 2:
    pytest.skip(msg="not yet ported to python3", allow_module_level=True)
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

    def test_rp_as_json(self):
        rp = ResearchProtocol(name="test_rp")
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)

        rp_json = rp.as_json()
        self.assertEqual(rp_json['name'], 'test_rp')
        self.assertTrue(rp_json['created_at'])
        self.assertTrue(rp_json['display_name'], 'Test Rp')

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
        self.assertEqual(1, len(org.research_protocols))
        self.assertEqual(org.research_protocols[0].id, rp.id)

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

        self.assertEqual(1, len(parent.research_protocols))
        self.assertEqual(parent.research_protocols[0].id, rp.id)
        self.assertEqual(0, len(child.research_protocols))
        self.assertEqual(child.research_protocol(as_of_date=datetime.utcnow()).id, rp.id)
