"""Model classes for retaining FHIR data"""
from enum import Enum
import json

from flask import abort, current_app

from ..date_tools import FHIR_datetime

BundleType = Enum(
    'BundleType',
    'document message transaction transaction-response batch batch-response '
    'history searchset collection')


def bundle_header_footer():
    """For building bundles in a sequential file format, return header/footer

    To write a large bundle to a file without holding all elements in memory,
    generate a header and footer split on the bundle's entry list, for
    sequential writes of each entry.
    """
    bundle = bundle_results(elements=[])
    bundle.pop("total")  # unknown in this context; not required
    split_at = 'entry": ['
    header, footer = json.dumps(bundle).split(split_at)
    header += split_at
    return header, footer


def bundle_results(elements, bundle_type=BundleType.searchset, links=None):
    """Generate FHIR Bundle from element lists

    :param elements: iterable of FHIR Resources to bundle
    :param bundle_type: limited by FHIR to be of the
      BundleType enum.
    :param links: links related to this bundle, such as API used to generate
    :returns: a FHIR compliant bundle

    """
    bundle = {
        'resourceType': 'Bundle',
        'updated': FHIR_datetime.now(),
        'total': len(elements),
        'type': bundle_type.name,
        'entry': elements,
    }
    if links:
        bundle['link'] = links
    return bundle


def v_or_n(value):
    """Return None unless the value contains data"""
    return value.rstrip() if value else None


def v_or_first(value, field_name):
    """Return desired from list or scalar value

    :param value: the raw data, may be a single value (directly
     returned) or a list from which the first element will be returned
    :param field_name: used in error text when multiple values
     are found for a constrained item.

    Some fields, such as `name` were assumed to always be a single
    dictionary containing single values, whereas the FHIR spec
    defines them to support 0..* meaning we must handle a list.

    NB - as the datamodel still only expects one, a 400 will be
    raised if given multiple values, using the `field_name` in the text.

    """
    if isinstance(value, (tuple, list)):
        if len(value) > 1:
            msg = "Can't handle multiple values for `{}`".format(field_name)
            current_app.logger.warn(msg)
            abort(400, msg)
        return value[0]
    return value
