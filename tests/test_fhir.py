"""Unit test module for fhir model"""
from datetime import datetime
from dateutil import parser, tz
from flask_webtest import SessionScope
import pytz
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.fhir import Coding, CodeableConcept, ValueQuantity
from portal.models.fhir import QuestionnaireResponse, FHIR_datetime

class TestFHIR(TestCase):
    """FHIR model tests"""

    def test_codeable_concept_codings(self):
        "CodeableConcepts should handle coding changes"
        initial_coding1 = Coding(system='sys1', code='ic-1', display='i1')
        initial_coding2 = Coding(system='sys2', code='ic-2', display='i2')
        cc = CodeableConcept(text='codings change',
                             codings=[initial_coding1, initial_coding2])
        with SessionScope(db):
            db.session.add(initial_coding1)
            db.session.add(initial_coding2)
            db.session.add(cc)
            db.session.commit()
        initial_coding1 = db.session.merge(initial_coding1)
        initial_coding2 = db.session.merge(initial_coding2)
        cc = db.session.merge(cc)

        # now parse a fhir snippet containing first just a partial set
        data = {"test_concept1":
                {"coding": [{"system": initial_coding1.system,
                             "code": initial_coding1.code,
                             "display": initial_coding1.display}, ],
                },
               }
        cc_parsed = CodeableConcept.from_fhir(data['test_concept1'])

        self.assertEquals(cc_parsed.codings, cc.codings)
        self.assertEquals(2, len(cc.codings))
        self.assertEquals(cc_parsed.text, cc.text)

        # and again, but now containing a new coding
        data = {"test_concept2":
                {"coding": [{"system": initial_coding1.system,
                             "code": initial_coding1.code,
                             "display": initial_coding1.display},
                            {"system": 'local',
                             "code": 'local-1',
                             "display": 'si-loco'}, ],
                 "text": "given two codings"
                },
               }
        cc_parsed = CodeableConcept.from_fhir(data['test_concept2'])

        persisted = CodeableConcept.query.get(cc_parsed.id)
        self.assertEquals(cc_parsed.codings, persisted.codings)
        self.assertEquals(len(persisted.codings), 3)
        self.assertEquals(persisted.text, 'given two codings')

    def test_codeable_concept_parse(self):
        system = "urn:ietf:bcp:47"
        code = "nl"
        display = "Dutch"
        data = {"language":
                {"coding": [{"system": system,
                             "code": code,
                             "display": display}, ],
                 "text": "Nederlands"
                },
               }
        cc = CodeableConcept.from_fhir(data['language'])
        self.assertEquals(cc.text, 'Nederlands')
        self.assertEquals(1, len(cc.codings))
        coding = cc.codings[0]
        self.assertEquals(coding.system, system)
        self.assertEquals(coding.code, code)
        self.assertEquals(coding.display, display)

    def test_vq_format(self):
        vq = ValueQuantity(units='widgets',
                           system='unknown', code='10.0')
        vq_str = "test format: {}".format(vq)
        self.assertIn('unknown', vq_str)
        self.assertIn('widgets', vq_str)
        self.assertIn('10.0', vq_str)

    def test_cc_format(self):
        c1 = Coding(system='http://test.org', code='66.5',
                             display='howdy')
        c2 = Coding(system='http://hl7.org', code='5-12',
                             display='grade')
        cc = CodeableConcept(text='test text', codings=[c1, c2])
        cc_str = "test format: {}".format(cc)
        self.assertIn(cc.text, cc_str)
        self.assertIn(c1.system, cc_str)
        self.assertIn(c1.code, cc_str)
        self.assertIn(c1.display, cc_str)
        self.assertIn(c2.system, cc_str)
        self.assertIn(c2.code, cc_str)
        self.assertIn(c2.display, cc_str)

    def test_qr_format(self):
        qr = QuestionnaireResponse(user_id=TEST_USER_ID,
                                   status='in-progress',
                                   authored=datetime.utcnow())
        db.session.add(qr)
        db.session.commit()
        qr_str = "test format: {}".format(qr)
        self.assertIn(str(qr.user_id), qr_str)
        self.assertIn(str(qr.status), qr_str)

    def test_tz_info(self):
        now = FHIR_datetime.now()
        parsed = parser.parse(now)
        # confirm it's in utc
        self.assertEquals(tz.tzutc(), parsed.tzinfo)

    def test_tz_aware_conversion(self):
        eastern = pytz.timezone('US/Eastern')
        aware = datetime(2016, 7, 15, 9, 20, 37, 0, eastern)
        parsed = FHIR_datetime.parse(aware.strftime("%Y-%m-%dT%H:%M:%S%z"))
        self.assertEquals(aware, parsed)
        self.assertEquals(pytz.utc, parsed.tzinfo)

    def test_tz_unaware_conversion(self):
        unaware = datetime(2016, 7, 15, 9, 20, 37, 0)
        parsed = FHIR_datetime.parse(unaware.strftime("%Y-%m-%dT%H:%M:%S"))
        self.assertEquals(unaware, parsed)
