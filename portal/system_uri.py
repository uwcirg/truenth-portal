"""Namespace module to house system URIs for use in FHIR"""

SNOMED = 'http://snomed.info/sct'
ICHOM = 'http://www.ichom.org/medical-conditions/localized-prostate-cancer/'
IETF_LANGUAGE_TAG = 'urn:ietf:bcp:47'
US_NPI = 'http://hl7.org/fhir/sid/us-npi'

# Our common, unique namespace
TRUENTH_NAMESPACE = 'http://us.truenth.org'

# Used for local clinical codes
TRUENTH_CLINICAL_CODE_SYSTEM = '{}/clinical-codes'.format(TRUENTH_NAMESPACE)
TRUENTH_ENCOUNTER_CODE_SYSTEM = '{}/encounter-types'.format(TRUENTH_NAMESPACE)

TRUENTH_QUESTIONNAIRE_CODE_SYSTEM = '{}/questionnaire'.format(TRUENTH_NAMESPACE)

# Auth identities - typically used with suffix for provider (i.e. google)
# or to name identity type (i.e. TrueNTH-username)
TRUENTH_IDENTITY_SYSTEM = '{}/identity-codes'.format(TRUENTH_NAMESPACE)
TRUENTH_EXTERNAL_SITE_SYSTEM = '{system}/external-site-id'.format(
    system=TRUENTH_IDENTITY_SYSTEM)
TRUENTH_EXTERNAL_STUDY_SYSTEM = '{system}/external-study-id'.format(
    system=TRUENTH_IDENTITY_SYSTEM)
TRUENTH_ID = '{system}/{provider}'.format(
    system=TRUENTH_IDENTITY_SYSTEM,
    provider='TrueNTH-identity')
TRUENTH_PI = '{system}/{provider}'.format(
    system=TRUENTH_IDENTITY_SYSTEM,
    provider='Primary-Investigator')
TRUENTH_USERNAME = '{system}/{provider}'.format(
    system=TRUENTH_IDENTITY_SYSTEM,
    provider='TrueNTH-username')
SUPPORTED_OAUTH_PROVIDERS = ('facebook', 'google')
TRUENTH_PROVIDER_SYSTEMS = tuple(
    '{system}/{provider}'.format(
        system=TRUENTH_IDENTITY_SYSTEM, provider=provider)
    for provider in SUPPORTED_OAUTH_PROVIDERS)

DECISION_SUPPORT_GROUP = '{}/decision-support-group'.format(
    TRUENTH_IDENTITY_SYSTEM)
PSA_TRACKER_GROUP = '{}/psa-tracker-group'.format(
    TRUENTH_IDENTITY_SYSTEM)
SYMPTOM_TRACKER_GROUP = '{}/symptom-tracker-group'.format(
    TRUENTH_IDENTITY_SYSTEM)
PRACTICE_REGION = '{}/practice-region'.format(TRUENTH_IDENTITY_SYSTEM)
SHORTCUT_ALIAS = '{}/shortcut-alias'.format(TRUENTH_IDENTITY_SYSTEM)
SHORTNAME_ID = '{}/shortname'.format(TRUENTH_IDENTITY_SYSTEM)
TRUENTH_RP_EXTENSION = '{}/research-protocol'.format(TRUENTH_IDENTITY_SYSTEM)
TRUENTH_STATUS_EXTENSION = '{}/status'.format(TRUENTH_IDENTITY_SYSTEM)
TRUENTH_VISIT_NAME_EXTENSION = '{}/visit-name'.format(TRUENTH_IDENTITY_SYSTEM)

TRUENTH_STRUCTURE_DEFINITION = '{}/fhir/StructureDefinition'.format(
    TRUENTH_NAMESPACE)

# Identifiers used in CommunicationRequests
TRUENTH_CR_NAME = '{}/communicationrequest/name'.format(
    TRUENTH_IDENTITY_SYSTEM)

# Local valuesets, where a decent published FHIR match could not be found
TRUENTH_VALUESET = '{}/fhir/valueset'.format(TRUENTH_NAMESPACE)

# Australian Institute of Health and Welfare's
# "National Health Data Dictionary 2012 version 16"
# Spec: http://www.aihw.gov.au/WorkArea/DownloadAsset.aspx?id=10737422824
# METeOR identifier: 291036
NHHD_291036 = "AU-NHHD-METeOR-id-291036"
TRUENTH_VALUESET_NHHD_291036 = "{}/{}".format(TRUENTH_VALUESET, NHHD_291036)
TRUENTH_EXTENSTION_NHHD_291036 = "{}/{}".format(
    TRUENTH_STRUCTURE_DEFINITION, NHHD_291036)
