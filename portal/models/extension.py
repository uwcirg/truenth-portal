"""Extension model"""
from abc import ABCMeta, abstractmethod, abstractproperty
from flask import abort
import pytz
from sqlalchemy.orm.exc import NoResultFound


class Extension:
    """Abstract base class for extension FHIR objects"""
    __metaclass__ = ABCMeta

    @abstractmethod
    def as_fhir(self):
        pass

    @abstractmethod
    def apply_fhir(self):
        pass


class CCExtension(Extension):
    """Abstract base class for extension FHIR objects with CC value sets"""
    __metaclass__ = ABCMeta

    @abstractproperty
    def children(self):  # pragma: no cover
        pass

    def as_fhir(self):
        if self.children.count():
            return {
                'url': self.extension_url,
                'valueCodeableConcept': {
                    'coding': [c.as_fhir() for c in self.children]}
            }

    def apply_fhir(self):
        from .fhir import Coding  # local due to cycle

        assert self.extension['url'] == self.extension_url
        # track current concepts - must remove any not requested
        remove_if_not_requested = {e.code: e for e in self.children}

        for coding in self.extension['valueCodeableConcept']['coding']:
            try:
                concept = Coding.query.filter_by(
                    system=coding['system'], code=coding['code']).one()
            except NoResultFound:
                raise ValueError("Unknown code: {} for system {}".format(
                                     coding['code'], coding['system']))
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
    def __init__(self, org, extension):
        self.source, self.extension = org, extension

    extension_url =\
        "http://hl7.org/fhir/StructureDefinition/user-timezone"

    def as_fhir(self):
        timezone = self.source.timezone
        if not timezone or timezone == 'None':
            timezone = 'UTC'
        return {'url': self.extension_url,
                'timezone': timezone}

    def apply_fhir(self):
        if self.extension['url'] != self.extension_url:
            raise ValueError('invalid url for OrganizationTimezone')
        if 'timezone' not in self.extension:
            abort(400, "Extension missing 'timezone' field")
        timezone = self.extension['timezone']

        # Confirm it's a recognized timezone
        try:
            pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            abort(400, "Unknown Timezone: '{}'".format(timezone))
        self.source.timezone = timezone

    @property
    def children(self):
        raise NotImplementedError
