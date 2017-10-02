"""Unit test module for Procedure API and model"""
from datetime import datetime, timedelta
import dateutil
from flask import current_app
import json
import os
import pytz
from sqlalchemy.orm.exc import NoResultFound
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.fhir import FHIR_datetime
from portal.models.procedure import Procedure
from portal.models.procedure_codes import latest_treatment_started_date
from portal.models.procedure_codes import known_treatment_not_started
from portal.models.procedure_codes import known_treatment_started
from portal.models.procedure_codes import TxStartedConstants
from portal.models.reference import Reference
from portal.system_uri import ICHOM, SNOMED, TRUENTH_CLINICAL_CODE_SYSTEM


class TestProcedure(TestCase):

    def test_procedureGET_404(self):
        self.add_procedure()
        self.login()
        rv = self.client.get('/api/patient/666/procedure')
        self.assert404(rv)

    def test_procedureGET(self):
        self.add_procedure()
        self.login()
        rv = self.client.get('/api/patient/%s/procedure' % TEST_USER_ID)

        data = json.loads(rv.data)
        self.assertEquals(
            '367336001',
            data['entry'][0]['resource']['code']['coding'][0]['code'])
        self.assertEquals(
            'Chemotherapy',
            data['entry'][0]['resource']['code']['coding'][0]['display'])
        self.assertEquals(
            Reference.patient(TEST_USER_ID).as_fhir()['reference'],
            data['entry'][0]['resource']['meta']['by']['reference'])
        last_updated = FHIR_datetime.parse(
            data['entry'][0]['resource']['meta']['lastUpdated'])
        self.assertAlmostEquals(
            datetime.utcnow(), last_updated, delta=timedelta(seconds=5))
        start_time = FHIR_datetime.parse(
            data['entry'][0]['resource']['performedPeriod']['start'])
        self.assertAlmostEquals(
            datetime.utcnow(), start_time, delta=timedelta(seconds=5))
        self.assertEquals(
            current_app.config.metadata.version,
            data['entry'][0]['resource']['meta']['version'])

    def test_procedure_from_fhir(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'procedure-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        proc = Procedure.from_fhir(data, Audit(user_id=TEST_USER_ID))
        self.assertEquals(
            proc.code.codings[0].system,
            'http://snomed.info/sct')
        self.assertEquals(proc.code.codings[0].code, '80146002')
        self.assertEquals(proc.start_time, dateutil.parser.parse("2013-04-05"))

    def test_procedure_bad_date(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'procedure-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)
        data['performedDateTime'] = '1843-07-01'  # can't handle pre 1900
        self.login()
        rv = self.client.post(
            '/api/procedure', content_type='application/json',
            data=json.dumps(data))
        self.assert400(rv)

        data['performedDateTime'] = '1943-17-01'  # month 17 doesn't fly
        rv = self.client.post(
            '/api/procedure', content_type='application/json',
            data=json.dumps(data))
        self.assert400(rv)

    def test_procedurePOST(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'procedure2-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        self.login()
        rv = self.client.post(
            '/api/procedure', content_type='application/json',
            data=json.dumps(data))

        results = json.loads(rv.data)
        proc_id = results['procedure_id']
        proc = Procedure.query.get(proc_id)
        self.assertEquals(
            proc.code.codings[0].system,
            'http://snomed.info/sct')
        self.assertEquals(proc.user_id, 1)
        self.assertEquals(proc.end_time, datetime(2011, 6, 27))
        self.assertEquals(proc.encounter.user_id, TEST_USER_ID)

    def test_timezone_procedure_POST(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'procedure2-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        # confirm we correctly convert a timezone aware datetime
        # to unaware but converted to UTC time
        start_time = "2013-01-28T13:31:00+01:00"
        end_time = "2013-01-28T14:27:00+01:00"
        data['performedPeriod']['start'] = start_time
        data['performedPeriod']['end'] = end_time

        self.login()
        rv = self.client.post(
            '/api/procedure', content_type='application/json',
            data=json.dumps(data))

        results = json.loads(rv.data)
        proc_id = results['procedure_id']
        proc = Procedure.query.get(proc_id)

        self.assertEquals(proc.start_time.tzinfo, None)
        self.assertEquals(proc.end_time.tzinfo, None)
        st = dateutil.parser.parse(start_time)
        st = st.astimezone(pytz.utc)
        st = st.replace(tzinfo=None)
        self.assertEquals(proc.start_time, st)

    def test_procedureDELETE(self):
        self.add_procedure()
        proc_id = Procedure.query.one().id
        self.login()
        rv = self.client.delete('/api/procedure/{}'.format(proc_id))
        self.assert200(rv)
        self.assertRaises(NoResultFound, Procedure.query.one)
        self.assertEquals(self.test_user.procedures.count(), 0)

    def test_treatment_started(self):
        # list of codes indicating 'treatment started' - handle accordingly
        started_codes = set([
            ('3', 'Radical prostatectomy (nerve-sparing)', ICHOM),
            ('3-nns', 'Radical prostatectomy (non-nerve-sparing)', ICHOM),
            ('4', 'External beam radiation therapy', ICHOM),
            ('5', 'Brachytherapy', ICHOM),
            ('6', 'Androgen deprivation therapy', ICHOM),
            ('7', 'Focal therapy', ICHOM),
            ('26294005', 'Radical prostatectomy (nerve-sparing)', SNOMED),
            ('26294005-nns', 'Radical prostatectomy (non-nerve-sparing)',
             SNOMED),
            ('33195004', 'External beam radiation therapy', SNOMED),
            ('228748004', 'Brachytherapy', SNOMED),
            ('707266006', 'Androgen deprivation therapy', SNOMED),
            ('888', u'Other (free text)', ICHOM),
            ('118877007', 'Procedure on prostate', SNOMED)
        ])
        # confirm we have the whole list:
        found = set()
        for codeableconcept in TxStartedConstants():
            [found.add((cc.code, cc.display, cc.system)) for cc in
             codeableconcept.codings]
        self.assertEquals(started_codes, found)

        # prior to setting any procedures, should return false
        self.assertFalse(known_treatment_started(self.test_user))

        for code, display, system in started_codes:
            self.add_procedure(code, display, system)
            self.test_user = db.session.merge(self.test_user)
            self.assertTrue(known_treatment_started(self.test_user),
                            "treatment {} didn't show as started".format(
                (system, code)))

            # The "others" count as treatement started, but should NOT
            # return a date from latest_treatment - only specific treatments
            if code in ('888', '118877007'):
                self.assertFalse(latest_treatment_started_date(self.test_user))
            else:
                self.assertTrue(latest_treatment_started_date(self.test_user))

            self.test_user.procedures.delete()  # reset for next iteration

    def test_treatment_not_started(self):
        # list of codes indicating 'treatment not started' - handle accordingly
        not_started_codes = (
            ('1', 'Watchful waiting', ICHOM),
            ('2', 'Active surveillance', ICHOM),
            ('373818007', 'Started watchful waiting', SNOMED),
            ('424313000', 'Started active surveillance', SNOMED),
            ('999', 'None', TRUENTH_CLINICAL_CODE_SYSTEM)
        )

        # prior to setting any procedures, should return false
        self.assertFalse(known_treatment_not_started(self.test_user))

        for code, display, system in not_started_codes:
            self.add_procedure(code, display, system)
            self.test_user = db.session.merge(self.test_user)
            self.assertTrue(known_treatment_not_started(self.test_user),
                            "treatment '{}' didn't show as not started".format(
                                (system, code)))
            self.test_user.procedures.delete()  # reset for next iteration
