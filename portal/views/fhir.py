"""FHIR namespaced endpoints, such as local valuesets"""
from flask import Blueprint, jsonify

from ..system_uri import NHHD_291036, TRUENTH_VALUESET_NHHD_291036

fhir_api = Blueprint('fhir_api', __name__, url_prefix='/fhir')


@fhir_api.route('/valueset/{}'.format(NHHD_291036))
def valueset_nhhd_291036():
    """Returns JSON representation of the TrueNTH subset of the valueset

    This valueset is used to define "indigenous status" from an Australian
    perspective.  It refers specifically to::

        Australian Institute of Health and Welfare's
        National Health Data Dictionary 2012 version 16
        Spec: http://www.aihw.gov.au/WorkArea/DownloadAsset.aspx?id=10737422824
        METeOR identifier: 291036

    See also `FHIR valuesets <https://www.hl7.org/FHIR/valueset.html>`_

    See also the background from the `pivotal issue
    <https://www.pivotaltracker.com/n/projects/1225464/stories/133560247>`_

    """
    valueset = {
        "resourceType": "ValueSet",
        "id": NHHD_291036,
        "url": TRUENTH_VALUESET_NHHD_291036,
        "name": (
            "Indigenous Status as defined by Australian Institute of Health "
            "and Welfare's National Health Data Dictionary 2012 version 1A6 "
            "Spec: "
            "http://www.aihw.gov.au/WorkArea/DownloadAsset.aspx?id=10737422824"
            " METeOR identifier: 291036"),
        "meta": {
            "lastUpdated": "2016-11-03T00:00:00.000Z"
        },
        "codeSystem": {
            "extension": [
                {"url": "http://hl7.org/fhir/StructureDefinition/valueset-oid",
                 "valueUri": "urn:oid:2.16.840.1.113883.5.104"
                 }
            ],
            "system": TRUENTH_VALUESET_NHHD_291036,
            "caseSensitive": "true",
            "concept": []
        }
    }

    concepts = valueset['codeSystem']['concept']
    for name, value in (
        ('Aboriginal but not Torres Strait Islander origin', '1'),
        ('Torres Strait Islander but not Aboriginal origin', '2'),
        ('Both Aboriginal and Torres Strait Islander origin', '3'),
        ('Neither Aboriginal nor Torres Strait Islander origin', '4'),
        ('Not stated/inadequately described', '9')
    ):
        concepts.append(
            {"code": value, "abstract": "false", "display": name,
             "definition": name})

    return jsonify(**valueset)
