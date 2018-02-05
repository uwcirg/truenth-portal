import json
from datetime import datetime
from tests import TestCase
from werkzeug.exceptions import BadRequest

from portal.date_tools import FHIR_datetime, RelativeDelta


class TestDateTools(TestCase):

    def test_relative_delta(self):
        d = {'months': 3, 'days': -14}
        rd = RelativeDelta(json.dumps(d))
        feb_15_leap_year = datetime.strptime('Feb 15 2016', '%b %d %Y')
        # feb + 3 = may; 15 - 14 = 1
        expected = datetime.strptime('May 1 2016', '%b %d %Y')
        self.assertEquals(feb_15_leap_year + rd, expected)

        # singular param raises error
        d = {'month': 5}
        with self.assertRaises(ValueError):
            rd = RelativeDelta(json.dumps(d))

    def test_int_date(self):
        # integer value shouldn't generate parser error
        acceptance_date = 1394413200000
        with self.assertRaises(BadRequest) as e:
            dt = FHIR_datetime.parse(acceptance_date, 'acceptance date')
        self.assertTrue('acceptance date' in str(e.exception))
