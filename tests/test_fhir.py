"""Unit test module for fhir model"""
from datetime import datetime
from flask.ext.webtest import SessionScope
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.fhir import CodeableConcept, ValueQuantity
from portal.models.fhir import QuestionnaireResponse


class TestFHIR(TestCase):
    """FHIR model tests"""

    def test_codeable_concept_parse(self):
        system = "urn:ietf:bcp:47"
        code = "nl"
        display = "Dutch"
        data = {"language":
                {"coding": [{"system": system,
                             "code": code,
                             "display": display}, ]
                }
               }
        cc = CodeableConcept.from_fhir(data['language'])
        self.assertEquals(cc.system, system)
        self.assertEquals(cc.code, code)
        self.assertEquals(cc.display, display)

    def test_vq_format(self):
        vq = ValueQuantity(units='widgets',
                           system='unknown', code='10.0')
        vq_str = "test format: {}".format(vq)
        self.assertIn('unknown', vq_str)
        self.assertIn('widgets', vq_str)
        self.assertIn('10.0', vq_str)

    def test_cc_format(self):
        cc = CodeableConcept(system='http://test.org', code='66.5',
                             display='howdy')
        cc_str = "test format: {}".format(cc)
        self.assertIn(cc.system, cc_str)
        self.assertIn(cc.code, cc_str)
        self.assertIn(cc.display, cc_str)

    def test_qr_format(self):
        qr = QuestionnaireResponse(user_id=TEST_USER_ID,
                                   status='in-progress',
                                   authored=datetime.utcnow())
        db.session.add(qr)
        db.session.commit()
        qr_str = "test format: {}".format(qr)
        self.assertIn(str(qr.user_id), qr_str)
        self.assertIn(str(qr.status), qr_str)
