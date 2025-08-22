""" TrueNTH Clinical Codes """
import json
import os
import requests

from ..database import db
from ..system_uri import (
    NHHD_291036,
    TRUENTH_CLINICAL_CODE_SYSTEM,
    TRUENTH_VALUESET,
)
from ..views.fhir import valueset_nhhd_291036
from .codeable_concept import CodeableConcept, Coding
from .encounter import EC
from .lazy import lazyprop
from .locale import LocaleConstants
from .value_quantity import ValueQuantity


class ClinicalConstants(object):
    __instance = None

    def __new__(cls):
        if ClinicalConstants.__instance is None:
            ClinicalConstants.__instance = object.__new__(cls)
        return ClinicalConstants.__instance

    def __iter__(self):
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            yield getattr(self, attr)

    @lazyprop
    def BIOPSY(self):
        coding = Coding(
            system=TRUENTH_CLINICAL_CODE_SYSTEM,
            code='111',
            display='biopsy',
        ).add_if_not_found(True)
        cc = CodeableConcept(codings=[coding, ]).add_if_not_found(True)
        assert coding in cc.codings
        return cc

    @lazyprop
    def PCaDIAG(self):
        coding = Coding(
            system=TRUENTH_CLINICAL_CODE_SYSTEM,
            code='121',
            display='PCa diagnosis',
        ).add_if_not_found(True)
        cc = CodeableConcept(codings=[coding, ]).add_if_not_found(True)
        assert coding in cc.codings
        return cc

    @lazyprop
    def PCaLocalized(self):
        coding = Coding(
            system=TRUENTH_CLINICAL_CODE_SYSTEM,
            code='141',
            display='PCa localized diagnosis',
        ).add_if_not_found(True)
        cc = CodeableConcept(codings=[coding, ]).add_if_not_found(True)
        assert coding in cc.codings
        return cc

    @lazyprop
    def TRUE_VALUE(self):
        value_quantity = ValueQuantity(
            value='true', units='boolean').add_if_not_found(True)
        return value_quantity

    @lazyprop
    def FALSE_VALUE(self):
        value_quantity = ValueQuantity(
            value='false', units='boolean').add_if_not_found(True)
        return value_quantity


CC = ClinicalConstants()


def parse_concepts(elements, system):
    """recursive function to build array of concepts from nested structure"""
    ccs = []
    for element in elements:
        ccs.append(Coding(code=element['code'],
                          display=element['display'],
                          system=system))
        if 'concept' in element:
            ccs += parse_concepts(element['concept'], system)
    return ccs


def fetch_HL7_V3_Namespace(valueSet, pull_from_hl7=False):
    """Pull and parse the published FHIR ethnicity namespace"""
    # NB, this used to be pulled on every deploy, but hl7.org now requires human
    # intervention, to bypass the captcha - now pulling cached version off file
    # system.
    src_url = 'http://hl7.org/fhir/STU3/v3/{valueSet}/v3-{valueSet}.cs.json'.format(
        valueSet=valueSet)
    if pull_from_hl7:
        response = requests.get(src_url)
        concept_source = response.json()
    else:
        cwd = os.path.dirname(__file__)
        fp = os.path.join(cwd, f'code_systems/v3-{valueSet}.cs.json')
        with open(fp, 'r') as jfile:
            concept_source = json.load(jfile)

    return parse_concepts(concept_source['concept'],
                          system='http://hl7.org/fhir/v3/{}'.format(valueSet))


def fetch_local_valueset(valueSet):
    """Pull and parse the named valueSet from our local definition"""
    response = valueset_nhhd_291036()
    return parse_concepts(response.json['codeSystem']['concept'],
                          system='{}/{}'.format(TRUENTH_VALUESET, valueSet))


def add_static_concepts(only_quick=False):
    """Seed database with default static concepts

    Idempotent - run anytime to push any new concepts into existing dbs

    :param only_quick: For unit tests needing quick loads, set true
        unless the test needs the slow to load race and ethnicity data.

    """
    from .procedure_codes import TxStartedConstants, TxNotStartedConstants

    concepts = fetch_local_valueset(NHHD_291036)
    if not only_quick:
        concepts += fetch_HL7_V3_Namespace('Ethnicity')
        concepts += fetch_HL7_V3_Namespace('Race')
    for concept in concepts:
        if not Coding.query.filter_by(code=concept.code,
                                      system=concept.system).first():
            db.session.add(concept)

    for clinical_concepts in CC:
        if clinical_concepts not in db.session():
            db.session.add(clinical_concepts)

    for encounter_type in EC:
        if encounter_type not in db.session():
            db.session.add(encounter_type)

    for concept in LocaleConstants():
        pass  # looping is adequate
    for concept in TxStartedConstants():
        pass  # looping is adequate
    for concept in TxNotStartedConstants():
        pass  # looping is adequate
