"""Module for additional datetime tools/utilities"""
from datetime import date, datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta
from flask import abort, current_app
import json
import pytz


def as_fhir(obj):
    """For builtin types needing FHIR formatting help

    Returns obj as JSON FHIR formatted string

    """
    if hasattr(obj, 'as_fhir'):
        return obj.as_fhir()
    if isinstance(obj, datetime):
        # Make SURE we only communicate unaware or UTC timezones
        tz = getattr(obj, 'tzinfo', None)
        if tz and tz != pytz.utc:
            current_app.logger.error("Datetime export of NON-UTC timezone")
        return obj.strftime("%Y-%m-%dT%H:%M:%S%z")
    if isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')


class FHIR_datetime(object):
    """Utility class/namespace for working with FHIR datetimes"""

    @staticmethod
    def as_fhir(obj):
        return as_fhir(obj)

    @staticmethod
    def parse(data, error_subject=None):
        """Parse input string to generate a UTC datetime instance

        NB - date must be more recent than year 1900 or a ValueError
        will be raised.

        :param data: the datetime string to parse
        :param error_subject: Subject string to use in error message

        :return: UTC datetime instance from given data

        """
        # As we use datetime.strftime for display, and it can't handle dates
        # older than 1900, treat all such dates as an error
        epoch = datetime.strptime('1900-01-01', '%Y-%m-%d')
        try:
            dt = parser.parse(data)
        except ValueError:
            msg = "Unable to parse {}: {}".format(error_subject, data)
            current_app.logger.warn(msg)
            abort(400, msg)
        if dt.tzinfo:
            # Convert to UTC if necessary
            if dt.tzinfo != pytz.utc:
                dt = dt.astimezone(pytz.utc)
            # Delete tzinfo for safe comparisons with other non tz aware objects
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
        return datetime.utcnow().isoformat()+'Z'


class RelativeDelta(relativedelta):
    """utility class to simplify storing relative deltas in SQL strings"""

    def __init__(self, paramstring):
        """Expects a JSON string of parameters

        :param paramstring: like '{\"months\": 3, \"days\": -14}' is parsed
            using JSON and passed to dateutl.relativedelta.  All parameters
            supported by relativedelta should work.

        :returns instance for use in date math such as:
            tomorrow = `utcnow() + RelativeDelta('{"days":1}')`

        """
        try:
            d = json.loads(paramstring)
        except ValueError:
            raise ValueError(
                "Unable to parse RelativeDelta value from `{}`".format(
                    paramstring))
        # for now, only using class for relative info, not absolute info
        if any(key[-1] != 's' for key, val in d.items()):
            raise ValueError(
                "Singular key found in RelativeDelta params: {}".format(
                    paramstring))
        super(RelativeDelta, self).__init__(**d)

    @staticmethod
    def validate(paramstring):
        """Simply try to bring one to life - or raise ValueError"""
        RelativeDelta(paramstring)
        return None


def localize_datetime(dt, user):
    if dt and user and user.timezone:
        local = pytz.utc.localize(dt)
        tz = pytz.timezone(user.timezone)
        return local.astimezone(tz)
    return dt
