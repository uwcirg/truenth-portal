"""Unit test module for Procedure API and model"""

from datetime import datetime, timedelta
import json
import os

import dateutil
from flask import current_app
import pytest
import pytz
from sqlalchemy.orm.exc import NoResultFound

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.fhir import FHIR_datetime
from portal.models.procedure import Procedure
from portal.models.procedure_codes import (
    TxStartedConstants,
    known_treatment_not_started,
    known_treatment_started,
    latest_treatment_started_date,
)
from portal.models.reference import Reference
from portal.system_uri import ICHOM, SNOMED, TRUENTH_CLINICAL_CODE_SYSTEM
from tests import TEST_USER_ID, TestCase


class TestProcedure(TestCase):

    def test_procedureGET_404(self):
        self.add_procedure()
        self.login()
        response = self.client.get('/api/patient/666/procedure')
        assert response.status_code == 404

    def test_procedureGET(self):
        self.add_procedure()
        self.login()
        response = self.client.get('/api/patient/%s/procedure' % TEST_USER_ID)

        data = response.json
        assert ('367336001'
                == data['entry'][0]['resource']['code']['coding'][0]['code'])
        assert ('Chemotherapy' ==
                data['entry'][0]['resource']['code']['coding'][0]['display'])
        assert (Reference.patient(TEST_USER_ID).as_fhir()['reference']
                == data['entry'][0]['resource']['meta']['by']['reference'])
        last_updated = FHIR_datetime.parse(
            data['entry'][0]['resource']['meta']['lastUpdated'])
        self.assertAlmostEqual(
            datetime.utcnow(), last_updated, delta=timedelta(seconds=5))
        start_time = FHIR_datetime.parse(
            data['entry'][0]['resource']['performedPeriod']['start'])
        self.assertAlmostEqual(
            datetime.utcnow(), start_time, delta=timedelta(seconds=5))
        assert (current_app.config.metadata['version']
                == data['entry'][0]['resource']['meta']['version'])

    def test_procedure_from_fhir(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'procedure-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        proc = Procedure.from_fhir(data, Audit(user_id=TEST_USER_ID))
        assert proc.code.codings[0].system == 'http://snomed.info/sct'
        assert proc.code.codings[0].code == '80146002'
        assert proc.start_time == dateutil.parser.parse("2013-04-05")

    def test_procedure_bad_date(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'procedure-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)
        data['performedDateTime'] = '1843-07-01'  # can't handle pre 1900
        self.login()
        response = self.client.post(
            '/api/procedure', content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 400

        data['performedDateTime'] = '1943-17-01'  # month 17 doesn't fly
        response = self.client.post(
            '/api/procedure', content_type='application/json',
            data=json.dumps(data))
        assert response.status_code == 400

    def test_procedurePOST(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'procedure2-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        self.login()
        response = self.client.post(
            '/api/procedure', content_type='application/json',
            data=json.dumps(data))

        results = response.json
        proc_id = results['procedure_id']
        proc = Procedure.query.get(proc_id)
        assert proc.code.codings[0].system == 'http://snomed.info/sct'
        assert proc.user_id == 1
        assert proc.end_time == datetime(2011, 6, 27)
        assert proc.encounter.user_id == TEST_USER_ID

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
        response = self.client.post(
            '/api/procedure', content_type='application/json',
            data=json.dumps(data))

        results = response.json
        proc_id = results['procedure_id']
        proc = Procedure.query.get(proc_id)

        assert proc.start_time.tzinfo is None
        assert proc.end_time.tzinfo is None
        st = dateutil.parser.parse(start_time)
        st = st.astimezone(pytz.utc)
        st = st.replace(tzinfo=None)
        assert proc.start_time == st

    def test_procedureDELETE(self):
        self.add_procedure()
        proc_id = Procedure.query.one().id
        self.login()
        response = self.client.delete('/api/procedure/{}'.format(proc_id))
        response.status_code == 200
        pytest.raises(NoResultFound, Procedure.query.one)
        assert self.test_user.procedures.count() == 0

    def test_treatment_started(self):
        # list of codes indicating 'treatment started' - handle accordingly
        started_codes = {
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
            ('888', 'Other (free text)', ICHOM),
            ('118877007', 'Procedure on prostate', SNOMED),
            ('999999999', 'Other primary treatment', SNOMED),
            ('androgen deprivation therapy - surgical orchiectomy',
             'Androgen deprivation therapy (ADT) - Surgical orchiectomy',
             TRUENTH_CLINICAL_CODE_SYSTEM),
            ('androgen deprivation therapy - chemical',
             'Androgen deprivation therapy (ADT) - Chemical',
             TRUENTH_CLINICAL_CODE_SYSTEM),
            ('176307007', 'Whole-gland ablation', SNOMED),
            ('438778003', 'Focal-gland ablation', SNOMED)

        }
        # confirm we have the whole list:
        found = set()
        for codeableconcept in TxStartedConstants():
            [found.add((cc.code, cc.display, cc.system)) for cc in
             codeableconcept.codings]
        assert started_codes == found

        # prior to setting any procedures, should return false
        assert not known_treatment_started(self.test_user)

        for code, display, system in started_codes:
            self.add_procedure(code, display, system)
            self.test_user = db.session.merge(self.test_user)
            assert known_treatment_started(self.test_user),\
                "treatment {} didn't show as started".format((system, code))

            # The "others" count as treatement started, but should NOT
            # return a date from latest_treatment - only specific treatments
            if code in ('888', '118877007'):
                assert not latest_treatment_started_date(self.test_user)
            else:
                assert latest_treatment_started_date(self.test_user)

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
        assert not known_treatment_not_started(self.test_user)

        for code, display, system in not_started_codes:
            self.add_procedure(code, display, system)
            self.test_user = db.session.merge(self.test_user)
            assert known_treatment_not_started(self.test_user), \
                "treatment '{}' didn't show as not started".format((system, code))
            self.test_user.procedures.delete()  # reset for next iteration
