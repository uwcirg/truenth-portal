"""Module for additional datetime tools/utilities"""
from datetime import date, datetime, timedelta
import json

from dateutil import parser
from dateutil.relativedelta import relativedelta
from flask import abort, current_app
from flask_babel import gettext as _
import pytz


def as_fhir(obj):
    """For builtin types needing FHIR formatting help

    Returns obj as JSON FHIR formatted string

    """
    if hasattr(obj, 'as_fhir'):
        return obj.as_fhir()
    if isinstance(obj, datetime):
        # Make SURE we only communicate UTC timezone aware objects
        tz = getattr(obj, 'tzinfo', None)
        if tz and tz != pytz.utc:
            current_app.logger.error("Datetime export of NON-UTC timezone")
        if not tz:
            utc_included = obj.replace(tzinfo=pytz.UTC)
        else:
            utc_included = obj
        # Chop microseconds from return (some clients can't handle parsing)
        final = utc_included.replace(microsecond=0)
        return final.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


class FHIR_datetime(object):
    """Utility class/namespace for working with FHIR datetimes"""

    @staticmethod
    def as_fhir(obj):
        return as_fhir(obj)

    @staticmethod
    def parse(data, error_subject=None, none_safe=False):
        """Parse input string to generate a UTC datetime instance

        NB - date must be more recent than year 1900 or a ValueError
        will be raised.

        :param data: the datetime string to parse
        :param error_subject: Subject string to use in error message
        :param none_safe: set true to sanely handle None values
         (None in, None out).  By default a 400 is raised.

        :return: UTC datetime instance from given data

        """
        if none_safe and data is None:
            return None

        # As we use datetime.strftime for display, and it can't handle dates
        # older than 1900, treat all such dates as an error
        epoch = datetime.strptime('1900-01-01', '%Y-%m-%d')
        try:
            dt = parser.parse(data)
        except (TypeError, ValueError) as e:
            msg = "Unable to parse {}: {}".format(error_subject, e)
            current_app.logger.warning(msg)
            abort(400, msg)
        if dt.tzinfo:
            # Convert to UTC if necessary
            if dt.tzinfo != pytz.utc:
                dt = dt.astimezone(pytz.utc)
            # Delete tzinfo for safe comparisons with other non tz aware objs
            # All datetime values stored in the db are expected to be in
            # UTC, and timezone unaware.
            dt = dt.replace(tzinfo=None)

        # As we use datetime.strftime for display, and it can't handle dates
        # older than 1900, treat all such dates as an error
        if dt < epoch:
            raise ValueError("Dates prior to year 1900 not supported")
        return dt

    @staticmethod
    def now():
        """Generates a FHIR compliant datetime string for current moment"""
        return datetime.utcnow().isoformat() + 'Z'


class RelativeDelta(relativedelta):
    """utility class to simplify storing relative deltas in SQL strings"""

    def __init__(self, paramstring=None, **kwargs):
        """Expects a JSON string of parameters

        :param paramstring: like '{\"months\": 3, \"days\": -14}' is parsed
            using JSON and passed to dateutl.relativedelta.  All parameters
            supported by relativedelta should work.
        :param kwargs: passed directly to relativedelta init - making copy
            constructors and the like function as base class.

        :returns instance for use in date math such as:
            tomorrow = `utcnow() + RelativeDelta('{"days":1}')`

        """
        if paramstring:
            try:
                d = json.loads(paramstring)
            except ValueError:
                raise ValueError(
                    "Unable to parse RelativeDelta value from `{}`".format(
                        paramstring))
            # for now, only using class for relative info, not absolute info
            if any(not key.endswith('s') for key, val in d.items()):
                raise ValueError(
                    "Singular key found in RelativeDelta params: {}".format(
                        paramstring))
        else:
            d = {}

        # confirm no collisions between param string and kwargs
        if kwargs and not set(d.keys()).isdisjoint(set(kwargs.keys())):
            raise ValueError(
                "collision with paramstring: {} and kwargs {}".format(
                    paramstring, kwargs))
        if kwargs:
            d.update(kwargs)
        super(RelativeDelta, self).__init__(**d)

    @staticmethod
    def validate(paramstring):
        """Simply try to bring one to life - or raise ValueError"""
        RelativeDelta(paramstring)
        return None


def localize_datetime(dt, user):
    """Localize given dt both in timezone and language

    :returns: datetime string in localized, printable format
      or empty string if given dt is None

    """
    if not dt:
        return ''
    if user and user.timezone:
        local = pytz.utc.localize(dt)
        tz = pytz.timezone(user.timezone)
        best = local.astimezone(tz)
    else:
        best = dt
    d, m, y = best.strftime('%-d %b %Y').split()
    return ' '.join((d, _(m), y))


def utcnow_sans_micro():
    """Returns datetime.utcnow() with 0 microseconds

    This is used by clients that don't need the microsecond accuracy,
    and found it problematic in practice.

    For example, some 3rd party clients can't handle parsing more than 3
    digits of microseconds - difficult to guess which way to round for
    all circumstances, and comparisons will fail should the db have a
    microsecond value, and one of the variables does not.

    By storing time values truncated to the nearest second, the return
    datetime from any API using ``date_tools.as_fhir()`` will reliably
    compare as expected.

    """
    now = datetime.utcnow()
    return now.replace(microsecond=0)


def weekday_delta(start, end):
    """Returns the datetime delta of end-start excluding weekends"""
    if end < start:
        raise ValueError("unexpected end date less than start")

    included_weekend_days = 0
    i = start
    while True:
        if i > end:
            break
        if i.isoweekday() > 5:
            included_weekend_days += 1
        i = i + timedelta(days=1)

    corrected_end = end - timedelta(days=included_weekend_days)
    return corrected_end - start
