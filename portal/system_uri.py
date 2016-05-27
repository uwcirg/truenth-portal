"""Namespace module to house system URIs for use in FHIR"""

# Used for local clinical codes
TRUENTH_CLINICAL_CODE_SYSTEM = 'http://us.truenth.org/clinical-codes'


# Auth identities - typically used with suffix for provider (i.e. google)
# or to name identity type (i.e. TrueNTH-username)
TRUENTH_IDENTITY_SYSTEM = 'http://us.truenth.org/identity-codes'
SHORTCUT_ALIAS = '/'.join((TRUENTH_IDENTITY_SYSTEM, 'shortcut-alias'))
