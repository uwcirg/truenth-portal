"""Namespace module to house system URIs for use in FHIR"""

# Our common, unique namespace
TRUENTH_NAMESPACE = 'http://us.truenth.org'

# Used for local clinical codes
TRUENTH_CLINICAL_CODE_SYSTEM = '{}/clinical-codes'.format(TRUENTH_NAMESPACE)

# Auth identities - typically used with suffix for provider (i.e. google)
# or to name identity type (i.e. TrueNTH-username)
TRUENTH_IDENTITY_SYSTEM = '{}/identity-codes'.format(TRUENTH_NAMESPACE)
SHORTCUT_ALIAS = '{}/shortcut-alias'.format(TRUENTH_IDENTITY_SYSTEM)

TRUENTH_STRUCTURE_DEFINITION = '{}/fhir/StructureDefinition'.format(
    TRUENTH_NAMESPACE)

# Local valuesets, where a decent published FHIR match could not be found
TRUENTH_VALUESET = '{}/fhir/valueset'.format(TRUENTH_NAMESPACE)

# Australian Standard Classification of Cultural and Ethnic Groups (ASCCEG)
TRUENTH_EXTENSTION_ASCCEG = '{}/ascceg'.format(TRUENTH_STRUCTURE_DEFINITION)
TRUENTH_VALUESET_ASCCEG = '{}/ascceg'.format(TRUENTH_VALUESET)
