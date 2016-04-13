"""Telecom Module

FHIR uses a telecom structure for email, fax, phone, etc.

"""
from flask import current_app

class Telecom(object):
    """Telecom model - not a formal db front at this time

    Several FHIR resources include telecom entries.  This helper
    class wraps common functions.

    """
    def __init__(self, phone=None, email=None, fax=None):
        self.phone = phone
        self.email = email
        self.fax = fax

    def __str__(self):
        return "Telecom: {0.phone} {0.email}".format(self)

    @classmethod
    def from_fhir(cls, data):
        telecom = cls()
        for item in data:
            attr = item['system']
            value = item['value']
            if not hasattr(telecom, attr):
                current_app.logger.warn(
                    "FHIR contains unexpected telecom system {system}"\
                    " ignoring {value}".format(**item))
            elif getattr(telecom, attr, None):
                current_app.logger.warn(
                    "FHIR contains multiple telecom entries for "\
                    "{system} ignoring {value}".format(**item))
            else:
                setattr(telecom, attr, value)
        return telecom

    def as_fhir(self):
        telecom = []
        for attr in ('phone', 'email', 'fax'):
            value = getattr(self, attr, None)
            if value:
                telecom.append({'system': attr,
                                'value': value})
        return telecom
