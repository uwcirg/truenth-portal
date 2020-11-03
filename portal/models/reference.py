"""Reference module - encapsulate FHIR Reference type"""
import re

from sqlalchemy import and_

from ..database import db
from ..system_uri import TRUENTH_QUESTIONNAIRE_CODE_SYSTEM, US_NPI
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
    def clinician(cls, clinician_id):
        """Create a reference object from a known id

        NB clinician is a user with the clinician role
        """
        instance = cls()
        instance.clinician_id = int(clinician_id)
        return instance

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
    def practitioner(cls, practitioner_id):
        """Create a reference object from a known practitioner id"""
        instance = cls()
        instance.practitioner_id = int(practitioner_id)
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
    def questionnaire_response(cls, qnr_identifier):
        """Create a reference from given questionnaire response identifier"""
        instance = cls()
        instance.questionnaire_response = (
            f"{qnr_identifier['system']}/QuestionnaireResponse/"
            f"{qnr_identifier['value']}")
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
        """Parse a Reference Object from a FHIR Reference resource

        Typical format: "{'Reference': 'Organization/12'}"
        or "{'reference': 'api/patient/6'}"

        FHIR is a little sloppy on upper/lower case, so this parser
        is also flexible.

        :returns: the referenced object - instantiated from the db

        :raises :py:exc:`portal.models.reference.MissingReference`: if
            the referenced object can not be found
        :raises :py:exc:`portal.models.reference.MultipleReference`: if
            the referenced object retrieves multiple results
        :raises :py:exc:`ValueError`: if the text format
            can't be parsed

        """
        # Due to cyclic import problems, keep these local
        from .organization import Organization, OrganizationIdentifier
        from .practitioner import Practitioner, PractitionerIdentifier
        from .questionnaire import Questionnaire, QuestionnaireIdentifier
        from .questionnaire_response import QuestionnaireResponse
        from .questionnaire_bank import QuestionnaireBank
        from .research_protocol import ResearchProtocol
        from .user import User

        def get_object_by_identifier(obj, system, value):
            if obj == Organization:
                query = obj.query.join(
                    OrganizationIdentifier).join(Identifier).filter(and_(
                        Organization.id
                        == OrganizationIdentifier.organization_id,
                        Identifier.id == OrganizationIdentifier.identifier_id,
                        Identifier.system == system,
                        Identifier._value == value))
            elif obj == Practitioner:
                query = obj.query.join(
                    PractitionerIdentifier).join(Identifier).filter(and_(
                        Practitioner.id
                        == PractitionerIdentifier.practitioner_id,
                        Identifier.id == PractitionerIdentifier.identifier_id,
                        Identifier.system == system,
                        Identifier._value == value))
            elif obj == Questionnaire:
                query = obj.query.join(
                    QuestionnaireIdentifier).join(Identifier).filter(and_(
                        Questionnaire.id ==
                        QuestionnaireIdentifier.questionnaire_id,
                        Identifier.id == QuestionnaireIdentifier.identifier_id,
                        Identifier.system == system,
                        Identifier._value == value))
            elif obj == QuestionnaireResponse:
                # NB the order of system, value is swaped with all other regex
                # patterns - swap back in identifier instance
                ident = Identifier(system=value, _value=system)
                query = obj.by_identifier(identifier=ident)
            else:
                raise ValueError(
                    '`{}` does not support external identifier '
                    'reference'.format(obj))
            if not query.count():
                raise MissingReference(
                    "Reference not found: {}".format(reference_text))
            elif query.count() > 1:
                raise MultipleReference(
                    'Multiple objects found for reference {}'.format(
                        reference_text))
            return query.first()

        if 'reference' in reference_dict:
            reference_text = reference_dict['reference']
        elif 'Reference' in reference_dict:
            reference_text = reference_dict['Reference']
        else:
            raise ValueError(
                '[R|r]eference key not found in reference {}'.format(
                    reference_dict))

        lookup = (
            (re.compile(r'[Cc]linician/(\d+)'), User, 'id'),
            (re.compile(r'[Oo]rganization/([^?]+)\?[Ss]ystem=(\S+)'),
             Organization, 'identifier'),
            (re.compile(r'[Oo]rganization/(\d+)'), Organization, 'id'),
            (re.compile(r'[Qq]uestionnaire/(\w+)\?[Ss]ystem=(\S+)'),
             Questionnaire, 'identifier'),
            (re.compile(r'[Qq]uestionnaire_[Bb]ank/(\w+[.]?\w*)'),
             QuestionnaireBank, 'name'),
            (re.compile(r'(\S+)/QuestionnaireResponse/(\S+)'),
             QuestionnaireResponse, 'identifier'),
            (re.compile(r'[Ii]ntervention/(\w+)'), Intervention, 'name'),
            (re.compile(r'[Pp]atient/(\d+)'), User, 'id'),
            (re.compile(r'[Pp]ractitioner/(\w+)\?[Ss]ystem=(\S+)'),
             Practitioner, 'identifier'),
            (re.compile(r'[Pp]ractitioner/(\d+)'), Practitioner, 'id'),
            (re.compile(r'[Rr]esearch_[Pp]rotocol/(.+)'),
             ResearchProtocol, 'name'))

        for pattern, obj, attribute in lookup:
            match = pattern.search(reference_text)
            if match:
                if attribute == 'identifier':
                    try:
                        id_system = match.groups()[1]
                        id_value = match.groups()[0]
                    except IndexError:
                        raise ValueError(
                            'Identifier values not found in reference '
                            '{}'.format(reference_text))
                    return get_object_by_identifier(obj, id_system, id_value)
                value = match.groups()[0]
                if attribute == 'id':
                    try:
                        value = int(value)
                    except ValueError:
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
        # local to avoid cyclic import
        from .organization import Organization
        from .practitioner import Practitioner
        from .user import User

        if hasattr(self, 'clinician_id'):
            ref = "api/clinician/{}".format(self.clinician_id)
            display = User.query.get(self.clinician_id).display_name
        if hasattr(self, 'patient_id'):
            ref = "api/patient/{}".format(self.patient_id)
            display = User.query.get(self.patient_id).display_name
        if hasattr(self, 'practitioner_id'):
            p = Practitioner.query.get(self.practitioner_id)
            i = [i for i in p.identifiers if i.system == US_NPI][0]
            ref = "api/practitioner/{}?system={}".format(i.value, i.system)
            display = p.display_name
        if hasattr(self, 'organization_id'):
            ref = "api/organization/{}".format(self.organization_id)
            display = Organization.query.get(self.organization_id).name
        if hasattr(self, 'questionnaire_name'):
            ref = "api/questionnaire/{}?system={}".format(
                self.questionnaire_name, TRUENTH_QUESTIONNAIRE_CODE_SYSTEM)
            display = self.questionnaire_name
        if hasattr(self, 'questionnaire_bank_name'):
            ref = "api/questionnaire_bank/{}".format(
                self.questionnaire_bank_name)
            display = self.questionnaire_bank_name
        if hasattr(self, 'questionnaire_response'):
            ref = self.questionnaire_response
            display = self.questionnaire_response
        if hasattr(self, 'research_protocol_name'):
            ref = "api/research_protocol/{}".format(
                self.research_protocol_name)
            display = self.research_protocol_name
        if hasattr(self, 'intervention_name'):
            ref = "api/intervention/{}".format(
                self.intervention_name)
            display = self.intervention_name

        return {"reference": ref, "display": display}
