"""Telecom Module

FHIR uses a telecom structure for email, fax, phone, etc.

"""
from flask import current_app

class Telecom(object):
    """Telecom model - not a formal db front at this time

    Several FHIR resources include telecom entries.  This helper
    class wraps common functions.

    """
    def __init__(self, phone=None, email=None, fax=None, alt_phone=None):
        self.phone = phone
        self.email = email
        self.fax = fax
        self.alt_phone = alt_phone

    def __str__(self):
        return "Telecom: {0.phone} {0.alt_phone} {0.email}".format(self)

    @classmethod
    def from_fhir(cls, data):
        telecom = cls()
        for item in data:
            attr = item.get('system')
            value = item.get('value')
            use = item.get('use')
            if not hasattr(telecom, attr):
                current_app.logger.warn(
                    "FHIR contains unexpected telecom system {system}"\
                    " ignoring {value}".format(**item))
            elif getattr(telecom, attr, None) and attr != 'phone':
                current_app.logger.warn(
                    "FHIR contains multiple telecom entries for "\
                    "{system} ignoring {value}".format(**item))
            elif use == 'home':
                setattr(telecom, 'alt_phone', value)
            else:
                setattr(telecom, attr, value)
        return telecom

    def as_fhir(self):
        telecom = []
        for attr in ('email', 'fax'):
            value = getattr(self, attr, None)
            if value:
                telecom.append({'system': attr,
                                'value': value})
        if self.phone:
            telecom.append({'system':'phone',
                            'value':self.phone,
                            'use':'mobile'})
        if self.alt_phone:
            telecom.append({'system':'phone',
                            'value':self.alt_phone,
                            'use':'home'})
        return telecom
