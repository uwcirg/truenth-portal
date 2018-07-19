"""Extension model"""
from abc import ABCMeta, abstractmethod, abstractproperty

from flask import abort
from future.utils import with_metaclass
import pytz

from .coding import Coding


class Extension(with_metaclass(ABCMeta, object)):
    """Abstract base class for extension FHIR objects"""

    @abstractmethod
    def as_fhir(self, include_empties=True):
        pass

    @abstractmethod
    def apply_fhir(self):
        pass


class CCExtension(with_metaclass(ABCMeta, Extension)):
    """Abstract base class for extension FHIR objects with CC value sets"""

    @abstractproperty
    def children(self):  # pragma: no cover
        pass

    def as_fhir(self, include_empties=True):
        if self.children.count():
            return {
                'url': self.extension_url,
                'valueCodeableConcept': {
                    'coding': [c.as_fhir() for c in self.children]}
            }
        # Return valid empty if none are currently defined and requested
        if include_empties:
            return {'url': self.extension_url}
        return None

    def apply_fhir(self):
        assert self.extension['url'] == self.extension_url
        # track current concepts - must remove any not requested
        remove_if_not_requested = {e.code: e for e in self.children}

        if 'valueCodeableConcept' in self.extension:
            for coding in self.extension['valueCodeableConcept']['coding']:
                concept = Coding.from_fhir(coding)
                assert concept
                if concept.code in remove_if_not_requested:
                    # The concept existed before and is to be retained
                    remove_if_not_requested.pop(concept.code)
                else:
                    # Otherwise, it's new; add it
                    self.children.append(concept)

        # Remove the stale concepts that weren't requested again
        for concept in remove_if_not_requested.values():
            self.children.remove(concept)


class TimezoneExtension(CCExtension):
    def __init__(self, source, extension):
        self.source, self.extension = source, extension

    extension_url = \
        "http://hl7.org/fhir/StructureDefinition/user-timezone"

    def as_fhir(self, include_empties=True):
        timezone = self.source.timezone
        if not timezone or timezone == 'None':
            timezone = 'UTC'
        return {'url': self.extension_url,
                'timezone': timezone}

    def apply_fhir(self):
        if self.extension['url'] != self.extension_url:
            raise ValueError('invalid url for OrganizationTimezone')
        timezone = self.extension.get('timezone')

        if timezone is not None:
            # Confirm it's a recognized timezone
            try:
                pytz.timezone(timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                abort(400, "Unknown Timezone: '{}'".format(timezone))
        self.source.timezone = timezone

    @property
    def children(self):
        raise NotImplementedError
