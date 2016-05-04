"""Reference module - encapsulate FHIR Reference type"""
import re

from ..extensions import db
import organization
import user

class MissingReference(Exception):
    """Raised when FHIR references cannot be found"""
    pass


class Reference(object):

    @classmethod
    def organization(cls, organization_id):
        """Create a reference object from a known organization id"""
        instance = cls()
        instance.organization_id = organization_id
        return instance

    @classmethod
    def patient(cls, patient_id):
        """Create a reference object from a known patient id"""
        instance = cls()
        instance.patient_id = patient_id
        return instance

    @classmethod
    def parse(cls, reference_dict):
        """Parse an organization from a FHIR Reference resource

        Typical format: "{'Reference': 'Organization/12'}"
        or "{'reference': 'api/patient/6'}"

        FHIR is a little sloppy on upper/lower case, so this parser
        is also flexible.

        :returns: the referenced object - instantiated from the db
        :raises MissingReference: if the referenced object can not be found
        :raises ValueError: if the text format can't be parsed

        """
        if 'reference' in reference_dict:
            reference_text = reference_dict['reference']
        elif 'Reference' in reference_dict:
            reference_text = reference_dict['reference']
        else:
            raise ValueError('[R|r]eference key not found in reference {}'.\
                    format(reference_dict))

        lookup = (
            (re.compile('[Oo]rganization/(\d+)'), organization.Organization),
            (re.compile('[Pp]atient/(\d+)'), user.User))

        for pattern, obj in lookup:
            match = pattern.search(reference_text)
            if match:
                try:
                    id = int(match.groups()[0])
                except:
                    raise ValueError('ID not found in reference {}'.format(
                        reference_text))
                with db.session.no_autoflush:
                    result = obj.query.get(id)
                if not result:
                    raise MissingReference("Reference not found: {}".format(
                        reference_text))
                return result

        raise ValueError('Reference not found: {}'.format(reference_text))

    def as_fhir(self):
        """Return FHIR compliant reference string

        FHIR uses the Reference Resource within a number of other
        resources to define things like who performed an observation
        or what organization another is a partOf.

        :returns: the appropriate JSON formatted reference string.

        """
        if hasattr(self, 'patient_id'):
            ref = "api/patient/{}".format(self.patient_id)
        if hasattr(self, 'organization_id'):
            ref = "api/organization/{}".format(self.organization_id)

        return {"reference": ref}
