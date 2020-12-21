"""Coredata Module

Core is a rather ambigious term - includes upfront questions such
as DOB and patient / staff role.  Basic diagnosis and procedure
questions.

Interventions will sometimes require their own set of data, for which the
`/api/coredata/*` endpoints exist.

"""
from abc import ABCMeta, abstractmethod
import sys

from flask import current_app

from .audit import Audit
from .clinical_constants import CC
from .intervention import INTERVENTION, UserIntervention
from .organization import Organization, OrgTree
from .procedure_codes import (
    known_treatment_not_started,
    known_treatment_started,
)
from .qb_status import patient_research_study_status
from .research_study import (
    EMPRO_RS_ID,
    ResearchStudy
)
from .role import ROLE
from .tou import ToU


class Coredata(object):
    """Singleton managing coredata **model** logic, mostly shortcuts"""

    class __singleton(object):
        """Hidden inner class defines all the public methods

        Outer class accessors wrap, so any calls hit the single
        instance and appear at outer class scope.
        """

        def __init__(self):
            self._registered = []

        def register_class(self, cls):
            if cls not in self._registered:
                self._registered.append(cls)

        def required(self, user, **kwargs):
            # Returns list of datapoints required for user
            items = []
            for cls in self._registered:
                instance = cls()
                if instance.required(user, **kwargs):
                    items.append(instance.id)
            return items

        def optional(self, user, **kwargs):
            # Returns list of optional datapoints for user
            items = []
            for cls in self._registered:
                instance = cls()
                if instance.optional(user, **kwargs):
                    items.append(instance.id)
            return items

        def initial_obtained(self, user, **kwargs):
            # Check if all registered methods have data
            for cls in self._registered:
                instance = cls()
                if not instance.required(user, **kwargs):
                    continue
                if instance.hasdata(user, **kwargs):
                    continue
                current_app.logger.debug(
                    'intial NOT obtained for at least {}'.format(cls.__name__))
                return False
            return True

        def still_needed(self, user, **kwargs):
            # Returns list of {field, collection_method} still needed
            needed = []
            for cls in self._registered:
                instance = cls()
                if not instance.required(user, **kwargs):
                    continue
                if not instance.hasdata(user, **kwargs):
                    d = {'field': instance.id}
                    method = instance.collection_method(user, **kwargs)
                    if method:
                        d['collection_method'] = method
                    needed.append(d)
            if needed:
                current_app.logger.debug(
                    'initial still needed for {}'.format(
                        [i['field'] for i in needed]))
            return needed

    instance = None

    def __new__(cls):
        if not Coredata.instance:
            Coredata.instance = Coredata.__singleton()
        return Coredata.instance

    @staticmethod
    def reset():
        del Coredata.instance
        Coredata.instance = None

    def __getattr__(self, name):
        """Delegate to hidden inner class"""
        return getattr(self.instance, name)

    def __setattr__(self, name, value):
        """Delegate to hidden inner class"""
        return setattr(self.instance, name, value)


class CoredataPoint(object, metaclass=ABCMeta):
    """Abstract base class - defining methods each datapoint needs"""

    @abstractmethod
    def required(self, user, **kwargs):
        """Returns true if required for user, false otherwise

        Applications are configured to request a set of core data points.
        This method returns True if the active configuration includes the
        datapoint for the user, regardless of whether or not a value has
        been acquired.  i.e., should the user ever be asked for this point,
        or should the control be hidden regardless of the presence of data.

        NB - the user's state is frequently considered.  For example,
        belonging to an intervention or organization may imply the datapoint
        should never be an available option for the user to set.

        Optional and required are mutually exclusive - an item may not be in
        either for a user, but it shouldn't be in both.

        """
        raise NotImplemented

    @abstractmethod
    def optional(self, user, **kwargs):
        """Returns true if optional for user, false otherwise

        Applications are configured to request a set of core data points.
        This method returns True if the active configuration includes the
        datapoint for the user, regardless of whether or not a value has
        been acquired.  i.e., should the user ever be asked for this point,
        or should the control be hidden regardless of the presence of data.

        NB - the user's state is frequently considered.  For example,
        belonging to an intervention or organization may imply the datapoint
        should never be an available option for the user to set.

        Optional and required are mutually exclusive - an item may not be in
        either for a user, but it shouldn't be in both.

        """
        raise NotImplemented

    @abstractmethod
    def hasdata(self, user, **kwargs):
        """Returns true if the data has been obtained, false otherwise"""
        raise NotImplemented

    @property
    def id(self):
        """Returns identifier for class - namely lowercase w/o Data suffix"""
        name = self.__class__.__name__
        return name[:-4].lower()

    def collection_method(self, user, **kwargs):
        """Returns None unless the item has a specialized method"""
        return None


def CP_user(user):
    """helper to determine if the user has Care Plan access"""
    return UserIntervention.user_access_granted(
        user_id=user.id,
        intervention_id=INTERVENTION.CARE_PLAN.id)


def SR_user(user):
    """helper to determine if the user has Sexual Recovery access"""
    return UserIntervention.user_access_granted(
        user_id=user.id,
        intervention_id=INTERVENTION.SEXUAL_RECOVERY.id)


def IRONMAN_user(user):
    """helper to determine if user is associated with the IRONMAN org"""
    # NB - not all systems have this organization!
    iron_org = Organization.query.filter_by(name='IRONMAN').first()
    if iron_org:
        OT = OrgTree()
        for org_id in (o.id for o in user.organizations if o.id):
            top_of_org = OT.find(org_id).top_level()
            if top_of_org == iron_org.id:
                return True
    return False


def enter_manually_interview_assisted(user, **kwargs):
    """helper to determine if we're in `enter manually - interview assisted`

    Looks for 'entry_method' in kwargs - returns true if it has value
    'interview assisted', false otherwise.

    """
    return kwargs.get('entry_method') == 'interview assisted'


def enter_manually_paper(user, **kwargs):
    """helper to determine if we're in `enter manually - paper`

    Looks for 'entry_method' in kwargs - returns true if it has value
    'paper', false otherwise.

    """
    return kwargs.get('entry_method') == 'paper'


# Series of "datapoint" collection classes follow

class DobData(CoredataPoint):

    def required(self, user, **kwargs):
        # DOB is only required for patient
        if user.has_role(ROLE.PATIENT.value):
            return True
        return False

    def optional(self, user, **kwargs):
        # Optional for anyone, for whom it isn't required
        return not self.required(user)

    def hasdata(self, user, **kwargs):
        return user.birthdate is not None


class RaceData(CoredataPoint):

    def required(self, user, **kwargs):
        return False

    def optional(self, user, **kwargs):
        if SR_user(user):
            return False
        if IRONMAN_user(user):
            return False
        if user.has_role(ROLE.PATIENT.value):
            return True
        return False

    def hasdata(self, user, **kwargs):
        return user.races.count() > 0


class EthnicityData(CoredataPoint):

    def required(self, user, **kwargs):
        return False

    def optional(self, user, **kwargs):
        if SR_user(user):
            return False
        if IRONMAN_user(user):
            return False
        if user.has_role(ROLE.PATIENT.value):
            return True
        return False

    def hasdata(self, user, **kwargs):
        return user.ethnicities.count() > 0


class IndigenousData(CoredataPoint):

    def required(self, user, **kwargs):
        return False

    def optional(self, user, **kwargs):
        if SR_user(user):
            return False
        if IRONMAN_user(user):
            return False
        if user.has_role(ROLE.PATIENT.value):
            return True
        return False

    def hasdata(self, user, **kwargs):
        return user.indigenous.count() > 0


class RoleData(CoredataPoint):

    def required(self, user, **kwargs):
        return not SR_user(user)

    def optional(self, user, **kwargs):
        return False

    def hasdata(self, user, **kwargs):
        if len(user.roles) > 0:
            return True


class OrgData(CoredataPoint):

    def required(self, user, **kwargs):
        if SR_user(user) or CP_user(user):
            return False
        if user.has_role(
                ROLE.PATIENT.value, ROLE.STAFF.value,
                ROLE.STAFF_ADMIN.value):
            return True
        return False

    def optional(self, user, **kwargs):
        return False

    def hasdata(self, user, **kwargs):
        return len(user.organizations) > 0


class ClinicalData(CoredataPoint):

    def required(self, user, **kwargs):
        if SR_user(user):
            return False
        return user.has_role(ROLE.PATIENT.value)

    def optional(self, user, **kwargs):
        return False

    def hasdata(self, user, **kwargs):
        required = {item: False for item in (
            CC.BIOPSY, CC.PCaDIAG)}

        for obs in user.observations:
            if obs.codeable_concept in required:
                required[obs.codeable_concept] = True

        return all(required.values())


class TreatmentData(CoredataPoint):

    def required(self, user, **kwargs):
        if SR_user(user):
            return False
        return user.has_role(ROLE.PATIENT.value)

    def optional(self, user, **kwargs):
        return False

    def hasdata(self, user, **kwargs):
        # procedure known to have started or not started by the user
        return known_treatment_not_started(user) or \
               known_treatment_started(user)

class LocalizedData(CoredataPoint):

    def required(self, user, **kwargs):
        if SR_user(user):
            return False
        if current_app.config.get('LOCALIZED_AFFILIATE_ORG'):
            # Some systems use organization affiliation to denote localized
            # on these systems, we don't ask about localized - let
            # the org check worry about that
            return False
        return user.has_role(ROLE.PATIENT.value)

    def optional(self, user, **kwargs):
        return False

    def hasdata(self, user, **kwargs):
        for obs in user.observations:
            if obs.codeable_concept == CC.PCaLocalized:
                return True
        return False


class NameData(CoredataPoint):

    def required(self, user, **kwargs):
        return not SR_user(user)

    def optional(self, user, **kwargs):
        return not self.required(user)

    def hasdata(self, user, **kwargs):
        return user.first_name and user.last_name


class TOU_core(CoredataPoint):
    """The flavors of Terms Of Use inherit from here to define the 'type'"""

    def required(self, user, **kwargs):
        return not SR_user(user)

    def optional(self, user, **kwargs):
        return False

    def hasdata(self, user, **kwargs):
        return ToU.query.join(Audit).filter(
            Audit.subject_id == user.id,
            ToU.type == self.tou_type,
            ToU.active.is_(True)).count() > 0

    def collection_method(self, user, **kwargs):
        """TOU collection may be specialized"""

        # if the user's top_level_org is associated with
        # ACCEPT_TERMS_ON_NEXT_ORG - the collection method
        # is "ACCEPT_ON_NEXT"
        org = current_app.config.get('ACCEPT_TERMS_ON_NEXT_ORG')
        if org:
            org = Organization.query.filter_by(name=org).one()
        if org and user.first_top_organization() == org:
            return "ACCEPT_ON_NEXT"
        return None


class Website_Terms_Of_UseData(TOU_core):
    tou_type = 'website terms of use'

    def required(self, user, **kwargs):
        if (not super(self.__class__, self).required(user, **kwargs) or
                enter_manually_paper(user, **kwargs) or
                enter_manually_interview_assisted(user, **kwargs)):
            return False
        return True


class Subject_Website_ConsentData(TOU_core):
    tou_type = 'subject website consent'

    def required(self, user, **kwargs):
        if not super(self.__class__, self).required(user, **kwargs):
            return False
        return user.has_role(ROLE.PATIENT.value)


class Empro_Website_Terms_Of_UseData(TOU_core):
    tou_type = 'EMPRO website terms of use'

    def required(self, user, **kwargs):
        if not super(self.__class__, self).required(user, **kwargs):
            return False
        research_study_status = patient_research_study_status(user)
        substudy_status = research_study_status[EMPRO_RS_ID] \
            if research_study_status else None
        substudy_assessment_is_ready = substudy_status \
            and substudy_status['ready']
        return user.has_role(ROLE.PATIENT.value) \
            and substudy_assessment_is_ready


class Stored_Website_Consent_FormData(TOU_core):
    tou_type = 'stored website consent form'

    def required(self, user, **kwargs):
        if (not super(self.__class__, self).required(user, **kwargs) or
                not enter_manually_interview_assisted(user, **kwargs)):
            return False
        return user.has_role(ROLE.PATIENT.value)


class Privacy_PolicyData(TOU_core):
    tou_type = 'privacy policy'

    def required(self, user, **kwargs):
        if (not super(self.__class__, self).required(user, **kwargs) or
                enter_manually_interview_assisted(user, **kwargs) or
                enter_manually_paper(user, **kwargs)):
            return False
        return True


def configure_coredata(app):
    """Configure app for coredata checks"""
    coredata = Coredata()

    # Add static list of "configured" datapoints
    config_datapoints = app.config.get(
        'REQUIRED_CORE_DATA', [
            'name', 'dob', 'role', 'org', 'clinical', 'localized',
            'treatment', 'race', 'ethnicity', 'indigenous',
            'website_terms_of_use', 'subject_website_consent',
            'stored_website_consent_form', 'privacy_policy',
            'empro_website_terms_of_use'
        ])

    for name in config_datapoints:
        # Camel case with 'Data' suffix - expect to find class in local
        # scope or raise exception
        cls_name = name.title() + 'Data'
        try:
            # limit class loading to this module - die if not found
            cls = getattr(sys.modules[__name__], cls_name)
        except AttributeError as e:
            app.logger.error(
                "Configuration for REQUIRED_CORE_DATA includes "
                "unknown element '{}' - can't continue".format(name))
            raise e
        coredata.register_class(cls)
