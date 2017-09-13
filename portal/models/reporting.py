"""Reporting statistics and data module"""
from collections import defaultdict

from ..dogpile import dogpile_cache
from .fhir import CC
from .intervention import Intervention
from .procedure_codes import known_treatment_started
from .procedure_codes import known_treatment_not_started
from .role import ROLE
from .user import User


@dogpile_cache.region('hourly')
def get_reporting_stats():
    """Cachable interface for expensive reporting data queries

    The following code is only run on a cache miss.

    """
    stats = {}
    stats['roles'] = defaultdict(int)
    stats['patients'] = defaultdict(int)
    stats['interventions'] = defaultdict(int)
    stats['intervention_access'] = defaultdict(int)
    stats['intervention_reports'] = defaultdict(int)
    stats['organizations'] = defaultdict(int)
    stats['registrations'] = []
    stats['encounters'] = defaultdict(list)

    interventions = Intervention.query.all()

    for user in User.query.filter_by(active=True):
        if ROLE.TEST in [r.name for r in user.roles]:
            continue

        for role in user.roles:
            stats['roles'][role.name] += 1
            if role.name == 'patient':
                if not any((obs.codeable_concept == CC.BIOPSY
                            and obs.value_quantity.value)
                           for obs in user.observations):
                    stats['patients']['pre-dx'] += 1
                elif known_treatment_not_started(user):
                    stats['patients']['dx-nt'] += 1
                elif known_treatment_started(user):
                    stats['patients']['dx-t'] += 1
                if any((obs.codeable_concept == CC.PCaLocalized
                        and obs.value_quantity == CC.FALSE_VALUE)
                       for obs in user.observations):
                    stats['patients']['meta'] += 1

        for interv in interventions:
            desc = interv.description
            if desc == 'Decision Support':
                desc = 'Decision Support P3P'
            if interv.display_for_user(user).access:
                stats['intervention_access'][desc] += 1
            if interv in user.interventions:
                stats['interventions'][desc] += 1
            if (any(doc.intervention == interv for doc in user.documents)):
                stats['intervention_reports'][desc] += 1

        if not user.organizations:
            stats['organizations']['Unspecified'] += 1
        else:
            for org in user.organizations:
                stats['organizations'][org.name] += 1

        stats['registrations'].append(user.registered)

        for enc in user.encounters:
            if enc.auth_method == 'password_authenticated':
                st = enc.start_time
                stats['encounters']['all'].append(st)
                for interv in user.interventions:
                    if interv.description == 'Decision Support':
                        stats['encounters']["Decision Support P3P"].append(st)
                    else:
                        stats['encounters'][interv.description].append(st)

    return stats