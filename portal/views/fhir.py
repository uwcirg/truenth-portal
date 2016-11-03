"""FHIR namespaced endpoints, such as local valuesets"""
from flask import Blueprint, jsonify

from ..system_uri import TRUENTH_VALUESET_ASCCEG


fhir_api = Blueprint('fhir_api', __name__, url_prefix='/fhir')

@fhir_api.route('/valueset/ascceg')
def valueset_ascceg():
    """Returns JSON representation of the TrueNTH subset of ASCCEG valueset

    The published FHIR valueset for race and ethnicities are US centric.
    The `Australian Standard Classification of Cultural and Ethnic Groups
    (ASCCEG)
    <http://www.abs.gov.au/ausstats/abs@.nsf/Latestproducts/1249.0Main%20Features212016?opendocument&tabname=Summary&prodno=1249.0&issue=2016&num=&view=>`_
    contains many values not in use, and the task of importing it all
    is too great at this time.

    This valueset represents exactly what is needed for certain clients.

    See also the background from the `pivotal issue
    <https://www.pivotaltracker.com/n/projects/1225464/stories/133560247>`_

    """

    # only using a small number from the offical ASCCEG data cube

    ascceg = {
        "resourceType": "ValueSet",
        "id": "us.truenth.org-ascceg",
        "url": TRUENTH_VALUESET_ASCCEG,
        "name": ("TrueNTH subset of the Australian Standard Classification "
                 "of Cultural and Ethnic Groups (ASCCEG)"),
        "meta": {
            "lastUpdated": "2016-11-02T00:00:00.000Z"
        },
        "codeSystem": {
            "extension": [
                {"url": "http://hl7.org/fhir/StructureDefinition/valueset-oid",
                 "valueUri": "urn:oid:2.16.840.1.113883.5.104"
                }
            ],
            "system": TRUENTH_VALUESET_ASCCEG,
            "caseSensitive": "true",
            "concept": []
        }
    }
    concepts = ascceg['codeSystem']['concept']
    for name, value in (('Australian Aboriginal', '1102'),
                        ('Torres Strait Islander', '1104'),
                        ('Aboriginal/Torres Strait Islander', '1102-1104'),
                        ('Non-indigenous', '1101'),
                        ('Other', '4999')):
        concepts.append({"code": value,
                         "abstract": "false",
                         "display": name,
                         "definition": name
                        })

    return jsonify(**ascceg)
