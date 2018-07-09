from __future__ import unicode_literals  # isort:skip

from datetime import datetime
import json

import pytest
from werkzeug.exceptions import BadRequest

from portal.date_tools import FHIR_datetime, RelativeDelta, localize_datetime
from tests import TestCase


def test_localize_datetime_none():
    assert localize_datetime(dt=None, user=None) == ''


def test_localize_datetime_no_user():
    input_date = datetime.strptime('Jun 01 2012', '%b %d %Y')
    expected = '1 Jun 2012'
    assert localize_datetime(dt=input_date, user=None) == expected


def test_relative_delta():
    d = {'months': 3, 'days': -14}
    rd = RelativeDelta(json.dumps(d))
    feb_15_leap_year = datetime.strptime('Feb 15 2016', '%b %d %Y')
    # feb + 3 = may; 15 - 14 = 1
    expected = datetime.strptime('May 1 2016', '%b %d %Y')
    assert feb_15_leap_year + rd == expected

    # singular param raises error
    d = {'month': 5}
    with pytest.raises(ValueError):
        rd = RelativeDelta(json.dumps(d))


class TestDateTools(TestCase):

    def test_int_date(self):
        # integer value shouldn't generate parser error
        acceptance_date = 1394413200000
        with pytest.raises(BadRequest) as e:
            dt = FHIR_datetime.parse(acceptance_date, 'acceptance date')
        assert 'acceptance date' in str(e)
