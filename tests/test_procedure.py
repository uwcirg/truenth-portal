"""Unit test module for Procedure API and model"""
from datetime import datetime, timedelta
import dateutil
from flask import current_app
from flask_webtest import SessionScope
import json
import os
import pytz
from sqlalchemy.orm.exc import NoResultFound
from tests import TestCase, TEST_USER_ID

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.fhir import Coding, CodeableConcept, FHIR_datetime
from portal.models.procedure import Procedure
from portal.models.reference import Reference


class TestProcedure(TestCase):

    def prep_db_for_procedure(self):
        # First push some procedure data into the db for the test user
        with SessionScope(db):
            audit = Audit(user_id=TEST_USER_ID)
            procedure = Procedure(audit=audit)
            coding = Coding(system='http://snomed.info/sct',
                            code='367336001',
                            display='Chemotherapy')
            code = CodeableConcept(codings=[coding,])
            procedure.code = code
            procedure.user = self.test_user
            procedure.start_time = datetime.utcnow()
            procedure.end_time = datetime.utcnow()
            db.session.add(procedure)
            db.session.commit()

    def test_procedureGET_404(self):
        self.prep_db_for_procedure()
        self.login()
        rv = self.app.get('/api/patient/666/procedure')
        self.assert404(rv)

    def test_procedureGET(self):
        self.prep_db_for_procedure()
        self.login()
        rv = self.app.get('/api/patient/%s/procedure' % TEST_USER_ID)

        data = json.loads(rv.data)
        self.assertEquals('367336001',
            data['entry'][0]['resource']['code']['coding'][0]['code'])
        self.assertEquals('Chemotherapy',
            data['entry'][0]['resource']['code']['coding'][0]['display'])
        self.assertEquals(
            Reference.patient(TEST_USER_ID).as_fhir(),
            data['entry'][0]['resource']['meta']['by'])
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
        self.assertEquals(proc.code.codings[0].system, 'http://snomed.info/sct')
        self.assertEquals(proc.code.codings[0].code, '80146002')
        self.assertEquals(proc.start_time, dateutil.parser.parse("2013-04-05"))

    def test_procedure_bad_date(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'procedure-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)
        data['performedDateTime'] = '1843-07-01'  # can't handle pre 1900
        self.login()
        rv = self.app.post(
            '/api/procedure', content_type='application/json',
            data=json.dumps(data))
        self.assert400(rv)

        data['performedDateTime'] = '1943-17-01'  # month 17 doesn't fly
        rv = self.app.post(
            '/api/procedure', content_type='application/json',
            data=json.dumps(data))
        self.assert400(rv)

    def test_procedurePOST(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'procedure2-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        self.login()
        rv = self.app.post(
            '/api/procedure', content_type='application/json',
            data=json.dumps(data))

        results = json.loads(rv.data)
        proc_id = results['procedure_id']
        proc = Procedure.query.get(proc_id)
        self.assertEquals(proc.code.codings[0].system, 'http://snomed.info/sct')
        self.assertEquals(proc.user_id, 1)
        self.assertEquals(proc.end_time, datetime(2011, 6, 27))

    def test_timezone_procedure_POST(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'procedure2-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        # confirm we correctly convert a timezone aware datetime
        # to unaware but converted to UTC time
        start_time ="2013-01-28T13:31:00+01:00"
        end_time = "2013-01-28T14:27:00+01:00"
        data['performedPeriod']['start'] = start_time
        data['performedPeriod']['end'] = end_time

        self.login()
        rv = self.app.post(
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
        self.prep_db_for_procedure()
        proc_id = Procedure.query.one().id
        self.login()
        rv = self.app.delete('/api/procedure/{}'.format(proc_id))
        self.assert200(rv)
        self.assertRaises(NoResultFound, Procedure.query.one)
        self.assertEquals(self.test_user.procedures.count(), 0)
