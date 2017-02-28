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
from portal.models.encounter import Encounter
from portal.models.reference import Reference
from portal.system_uri import ICHOM, SNOMED, TRUENTH_CLINICAL_CODE_SYSTEM


class TestProcedure(TestCase):

    def test_procedure_from_fhir(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'encounter-example.json'), 'r') as fhir_data:
            data = json.load(fhir_data)

        enc = Encounter.from_fhir(data, Audit(user_id=TEST_USER_ID))
        self.assertEquals(enc.status, 'finished')
        self.assertEquals(enc.auth_method, 'password_authenticated')
        self.assertEquals(enc.start_time, dateutil.parser.parse("2013-05-05"))

    def test_procedure_as_fhir(self):
        enc = Encounter(status='planned', auth_method='url_authenticated',
                        user_id=TEST_USER_ID,
                        start_time=dateutil.parser.parse("2013-07-07"))
        data = enc.as_fhir()
        self.assertEquals(enc.status, data['status'])
        self.assertEquals(enc.auth_method, data['auth_method'])

