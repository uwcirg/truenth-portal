from datetime import datetime, timedelta
import json

import pytest
from werkzeug.exceptions import BadRequest

from portal.date_tools import (
    FHIR_datetime,
    RelativeDelta,
    localize_datetime,
    weekday_delta,
)


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


def test_multiply_rd():
    d = {'months': 3}
    rd = RelativeDelta(json.dumps(d), years=1)
    assert rd.years == 1
    assert rd.months == 3
    times3 = 3 * rd
    assert times3.years == 3
    assert times3.months == 9


def test_rd_param_collision():
    d = {'months': 3}
    with pytest.raises(ValueError):
        RelativeDelta(json.dumps(d), months=4)


def test_int_date(app_logger):
    # integer value shouldn't generate parser error
    acceptance_date = 1394413200000
    with pytest.raises(BadRequest) as e:
        dt = FHIR_datetime.parse(acceptance_date, 'acceptance date')
    assert 'acceptance date' in str(e.value)


def test_weekday_count():
    monday = datetime.strptime("2021-01-04T12:00:00Z", "%Y-%m-%dT%H:%M:%SZ")
    friday = datetime.strptime("2021-01-08T12:00:00Z", "%Y-%m-%dT%H:%M:%SZ")
    assert weekday_delta(monday, friday) == timedelta(days=4)


def test_weekday_count_skips_weekends():
    monday = datetime.strptime("2021-01-04T12:00:00Z", "%Y-%m-%dT%H:%M:%SZ")
    next_monday = datetime.strptime("2021-01-11T12:00:00Z", "%Y-%m-%dT%H:%M:%SZ")
    assert weekday_delta(monday, next_monday) == timedelta(days=5)
