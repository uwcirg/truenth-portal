"""Reference module - encapsulate FHIR Reference type"""
import re
from sqlalchemy import and_

from ..database import db
from .identifier import Identifier
from .intervention import Intervention


class MissingReference(Exception):
    """Raised when FHIR references cannot be found"""
    pass


class MultipleReference(Exception):
    """Raised when FHIR references retrieve multiple results"""
    pass


class Reference(object):

    def __repr__(self):
        result = ['Reference(']
        for attr in self.__dict__:
            if not attr.startswith('_'):
                result.append('{}={}'.format(attr, getattr(self, attr)))
        result.append(')')
        return ''.join(result)

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
    def questionnaire_bank(cls, questionnaire_bank_name):
        """Create a reference object from a known questionnaire bank"""
        instance = cls()
        instance.questionnaire_bank_name = questionnaire_bank_name
        return instance

    @classmethod
    def research_protocol(cls, research_protocol_name):
        """Create a reference object from a known research protocol"""
        instance = cls()
        instance.research_protocol_name = research_protocol_name
        return instance

    @classmethod
    def intervention(cls, intervention_id):
        """Create a reference object from given intervention

        Intervention references maintained by name - lookup from given id.

        """
        instance = cls()
        obj = Intervention.query.get(intervention_id)
        instance.intervention_name = obj.name
        return instance

    @classmethod
    def parse(cls, reference_dict):
        """Parse an organization from a FHIR Reference resource

        Typical format: "{'Reference': 'Organization/12'}"
        or "{'reference': 'api/patient/6'}"

        FHIR is a little sloppy on upper/lower case, so this parser
        is also flexible.

        :returns: the referenced object - instantiated from the db

        :raises :py:exc:`portal.models.reference.MissingReference`: if
            the referenced object can not be found
        :raises :py:exc:`portal.models.reference.MultipleReference`: if
            the referenced object retrieves multiple results
        :raises :py:exc:`exceptions.ValueError`: if the text format
            can't be parsed

        """
        # Due to cyclic import problems, keep these local
        from .organization import Organization, OrganizationIdentifier
        from .questionnaire import Questionnaire
        from .questionnaire_bank import QuestionnaireBank
        from .research_protocol import ResearchProtocol
        from .user import User

        if 'reference' in reference_dict:
            reference_text = reference_dict['reference']
        elif 'Reference' in reference_dict:
            reference_text = reference_dict['Reference']
        else:
            raise ValueError(
                '[R|r]eference key not found in reference {}'.format(
                    reference_dict))

        lookup = (
            (re.compile('[Oo]rganization/(\d+)'), Organization, 'id'),
            (re.compile('[Qq]uestionnaire/(\w+)'), Questionnaire, 'name'),
            (re.compile('[Qq]uestionnaire_[Bb]ank/(\w+)'),
             QuestionnaireBank, 'name'),
            (re.compile('[Ii]ntervention/(\w+)'), Intervention, 'name'),
            (re.compile('[Pp]atient/(\d+)'), User, 'id'),
            (re.compile('[Rr]esearch_[Pp]rotocol/(\w+)'),
             ResearchProtocol, 'name'))

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

        match = re.compile('[Oo]rganization/(.+)/(.+)').search(reference_text)
        if match:
            try:
                id_system = match.groups()[0]
                id_value = match.groups()[1]
            except:
                raise ValueError(
                    'Identifier values not found in reference {}'.format(
                        reference_text))
            with db.session.no_autoflush:
                result = Organization.query.join(
                      OrganizationIdentifier).join(Identifier).filter(and_(
                          Organization.id ==
                          OrganizationIdentifier.organization_id,
                          OrganizationIdentifier.identifier_id ==
                          Identifier.id,
                          Identifier.system == id_system,
                          Identifier._value == id_value))
            if not result.count():
                raise MissingReference("Reference not found: {}".format(
                    reference_text))
            elif result.count() > 1:
                raise MultipleReference(
                    'Multiple organizations found for reference {}'.format(
                        reference_text))
            return result.first()

        raise ValueError('Reference not found: {}'.format(reference_text))

    def as_fhir(self):
        """Return FHIR compliant reference string

        FHIR uses the Reference Resource within a number of other
        resources to define things like who performed an observation
        or what organization another is a partOf.

        :returns: the appropriate JSON formatted reference string.

        """
        from .organization import Organization  # local to avoid cyclic import
        from .user import User  # local to avoid cyclic import

        if hasattr(self, 'patient_id'):
            ref = "api/patient/{}".format(self.patient_id)
            display = User.query.get(self.patient_id).display_name
        if hasattr(self, 'organization_id'):
            ref = "api/organization/{}".format(self.organization_id)
            display = Organization.query.get(self.organization_id).name
        if hasattr(self, 'questionnaire_name'):
            ref = "api/questionnaire/{}".format(self.questionnaire_name)
            display = self.questionnaire_name
        if hasattr(self, 'questionnaire_bank_name'):
            ref = "api/questionnaire_bank/{}".format(
                self.questionnaire_bank_name)
            display = self.questionnaire_bank_name
        if hasattr(self, 'research_protocol_name'):
            ref = "api/research_protocol/{}".format(
                self.research_protocol_name)
            display = self.research_protocol_name
        if hasattr(self, 'intervention_name'):
            ref = "api/intervention/{}".format(
                self.intervention_name)
            display = self.intervention_name

        return {"reference": ref, "display": display}
