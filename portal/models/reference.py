"""Reference module - encapsulate FHIR Reference type"""
import re

from ..database import db

class MissingReference(Exception):
    """Raised when FHIR references cannot be found"""
    pass


class Reference(object):

    @classmethod
    def organization(cls, organization_id):
        """Create a reference object from a known organization id"""
        instance = cls()
        instance.organization_id = int(organization_id)
        return instance

    @classmethod
    def patient(cls, patient_id):
        """Create a reference object from a known patient id"""
        instance = cls()
        instance.patient_id = int(patient_id)
        return instance

    @classmethod
    def questionnaire(cls, questionnaire_name):
        """Create a reference object from a known questionnaire name"""
        instance = cls()
        instance.questionnaire_name = questionnaire_name
        return instance

    @classmethod
    def parse(cls, reference_dict):
        """Parse an organization from a FHIR Reference resource

        Typical format: "{'Reference': 'Organization/12'}"
        or "{'reference': 'api/patient/6'}"

        FHIR is a little sloppy on upper/lower case, so this parser
        is also flexible.

        :returns: the referenced object - instantiated from the db

        :raises :py:exc:`portal.models.reference.MissingReference`: if the referenced object can not be found
        :raises :py:exc:`exceptions.ValueError`: if the text format can't be parsed

        """
        ## Due to cyclic import problems, keep these local
        from .organization import Organization
        from .questionnaire import Questionnaire
        from .user import User


        if 'reference' in reference_dict:
            reference_text = reference_dict['reference']
        elif 'Reference' in reference_dict:
            reference_text = reference_dict['Reference']
        else:
            raise ValueError('[R|r]eference key not found in reference {}'.\
                    format(reference_dict))

        lookup = (
            (re.compile('[Oo]rganization/(\d+)'), Organization, 'id'),
            (re.compile('[Qq]uestionnaire/(\w+)'), Questionnaire, 'name'),
            (re.compile('[Pp]atient/(\d+)'), User, 'id'))

        for pattern, obj, attribute in lookup:
            match = pattern.search(reference_text)
            if match:
                value = match.groups()[0]
                if attribute == 'id':
                    try:
                        value = int(value)
                    except:
                        raise ValueError('ID not found in reference {}'.format(
                            reference_text))
                with db.session.no_autoflush:
                    search_attr = {attribute: value}
                    result = obj.query.filter_by(**search_attr).first()
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
        if hasattr(self, 'questionnaire_name'):
            ref = "api/questionnaire/{}".format(self.questionnaire_name)

        return {"reference": ref}
