"""Coredata Module

Core is a rather ambigious term - includes upfront questions such
as DOB and patient / provider role.  Basic diagnosis and procedure
questions.

Interventions will sometimes require their own set of data, for which the
`/api/coredata/*` endpoints exist.

"""
from abc import ABCMeta, abstractmethod

from .audit import Audit
from .fhir import CC
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
            self._registered.append(cls)

        def initial_obtained(self, user):
            # Check if all registered methods have data
            for cls in self._registered:
                if cls().hasdata(user):
                    continue
                return False
            return True

    instance = None
    def __new__(cls):
        if not Coredata.instance:
            Coredata.instance = Coredata.__singleton()
        return Coredata.instance

    def __getattr__(self, name):
        """Delegate to hidden inner class"""
        return getattr(self.instance, name)

    def __setattr__(self, name):
        """Delegate to hidden inner class"""
        return setattr(self.instance, name)


class CoredataPoint(object):
    """Abstract base class - defining methods each datapoint needs"""
    __metaclass__ = ABCMeta

    @abstractmethod
    def hasdata(self, user):
        """Returns true if the data has been obtained, false otherwise"""
        raise NotImplemented

###
## Series of "datapoint" collection classes follow
###


class DobData(CoredataPoint):
    def hasdata(self, user):
        # DOB is only required for patient and partner
        roles = (r.name for r in user.roles)
        if ROLE.PATIENT in roles or ROLE.PARTNER in roles: 
            return user.birthdate is not None
        else:
            # If they haven't set a role, we don't know if we care yet
            return len(user.roles) > 0


class RoleData(CoredataPoint):
    def hasdata(self, user):
        """Does user have at least one role?"""
        if len(user.roles) > 0:
            return True


class OrgData(CoredataPoint):
    def hasdata(self, user):
        """Does user have at least one org?

        Special "none of the above" org still counts.
        """
        if user.organizations.count() > 0:
            return True


class ClinicalData(CoredataPoint):
    def hasdata(self, user):
        """only need clinical data from patients"""
        if ROLE.PATIENT not in (r.name for r in user.roles) :
            # If they haven't set a role, we don't know if we care yet
            return len(user.roles) > 0

        required = {item: False for item in (
            CC.BIOPSY, CC.PCaDIAG, CC.TX, CC.PCaLocalized)}

        for obs in user.observations:
            if obs.codeable_concept in required:
                required[obs.codeable_concept] = True
        return all(required.values())


class TouData(CoredataPoint):
    def hasdata(self, user):
        return  ToU.query.join(Audit).filter(
            Audit.user_id==user.id).count() > 0


def configure_coredata(app):
    """Configure app for coredata checks"""
    coredata = Coredata()

    # Add static list of "configured" datapoints
    for cls in (DobData, RoleData, OrgData, ClinicalData, TouData):
        coredata.register_class(cls)
