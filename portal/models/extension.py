"""Extension model"""
from abc import ABCMeta, abstractmethod, abstractproperty

from flask import abort
import pytz

from .coding import Coding


class Extension(object, metaclass=ABCMeta):
    """Abstract base class for extension FHIR objects"""

    @abstractmethod
    def as_fhir(self, include_empties=True):
        pass

    @abstractmethod
    def apply_fhir(self):
        pass


class CCExtension(Extension, metaclass=ABCMeta):
    """Abstract base class for extension FHIR objects with CC value sets"""

    @abstractproperty
    def children(self):  # pragma: no cover
        pass

    def as_fhir(self, include_empties=True, include_inherited=False):
        if self.children.count():
            return {
                'url': self.extension_url,
                'valueCodeableConcept': {
                    'coding': [c.as_fhir() for c in self.children]}
            }
        if include_empties:
            # Return valid empty if none are currently defined and requested
            return {'url': self.extension_url}

        if include_inherited:
            # TODO in the organization instance, need a `parent()`
            #  implementation, and to climb tree till exhaused or value
            return None

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

    def as_fhir(self, include_empties=True, include_inherited=False):
        # Include inherited is NOP in this case, as self.source.timezone
        # does its own inheritance lookup
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
