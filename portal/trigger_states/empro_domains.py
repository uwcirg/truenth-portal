"""Module to handle complexity of domain scoring and triggers"""
from collections import defaultdict

from ..models.observation import Observation
from ..models.questionnaire_response import first_last_like_qnr

# TODO extract from EMPRO Questionnaire - hardcoded for time being
EMPRO_DOMAINS = (
    'general_pain', 'joint_pain', 'insomnia', 'fatigue', 'anxious',
    'discouraged', 'sad', 'social_isolation')


class AnswerIdValue(object):
    """Simple container to hold identifier and value for an answer"""
    def __init__(self, id, value):
        self.id = id
        self.value = value


class DomainTriggers(object):
    """Handles only the trigger calc, from question ID and value internals

    To calculate triggers within a domain, we need question identifiers and
    values.  Given such, calculate the trigger state for any given domain.
    """

    def __init__(
            self, domain, current_answers, previous_answers, initial_answers):
        self.domain = domain
        self._triggers = dict()

        # Dictionaries (possibly empty) keyed by question link_id, containing
        # tuple (answer value, severity)
        self.current_answers = current_answers or dict()
        self.previous_answers = previous_answers or dict()
        self.initial_answers = initial_answers or dict()

    @property
    def triggers(self):
        self.eval()
        return self._triggers

    def check_for_worsening(self, previous, current):
        """Helper to look for worsening conditions"""
        keyset = set(list(previous.keys()) + list(current.keys()))
        for link_id in keyset:
            if link_id not in previous or link_id not in current:
                # Without an answer in both, can't compare
                continue

            # format: (score, severity)
            prev_value, _ = previous[link_id]
            curr_value, _ = current[link_id]
            if prev_value < curr_value:
                # don't overwrite w/ soft if hard value already exists
                if link_id not in self._triggers:
                    self._triggers[link_id] = 'soft'
                if prev_value + 1 < curr_value:
                    self._triggers[link_id] = 'hard'

    def eval(self):
        """Use instance data to evaluate trigger state for domain"""
        # consider caching - for now, recalc when called
        self._triggers.clear()

        # check if current data includes hard trigger
        for link_id, v_tup in self.current_answers.items():
            # format: (score, severity)
            _, severity = v_tup
            if severity and severity in ('penultimate', 'ultimate'):
                self._triggers[link_id] = 'hard'

        # if we have a previous or initial, see if anything worsened
        if self.previous_answers:
            self.check_for_worsening(
                self.previous_answers, self.current_answers)

        if self.initial_answers:
            self.check_for_worsening(
                self.initial_answers, self.current_answers)


class DomainManifold(object):
    """Bring together available responses and domains for trigger eval"""

    def __init__(self, qnr):
        self.initial_qnr, self.prev_qnr, self.cur_qnr = None, None, None
        self.initial_obs, self.prev_obs, self.cur_obs = None, None, None
        self.obtain_observations(qnr)

    def obtain_observations(self, qnr):
        self.cur_qnr = qnr
        self.initial_qnr, self.prev_qnr = first_last_like_qnr(qnr)

        for timepoint in 'cur', 'initial', 'prev':
            process_qnr = getattr(self, f"{timepoint}_qnr")
            if process_qnr:
                obs = Observation.query.filter(
                    Observation.derived_from == str(process_qnr.id)
                )
                # Extract useful bits for trigger calc from observations
                # format as dictionary, keyed by `domain`.  Each domain
                # will contain a dictionary keyed by `link_id`, with a value
                # tuple (score, severity)
                results = dict()
                for ob in obs:
                    # acquire the domain
                    for code in ob.codeable_concept.codings:
                        if code.system == 'http://us.truenth.org/observation':
                            domain = code.code
                    if not domain:
                        raise ValueError(
                            f"'domain' not found in observation {ob.id}")
                    link_id, score = ob.value_coding.code.rsplit('.', 1)
                    # severity is only present on penultimate, ultimate
                    severity = None
                    if ob.value_coding.extension_id:
                        severity = ob.value_coding.extension.code
                    if domain not in results:
                        results[domain] = defaultdict(dict)
                    results[domain][link_id] = (int(score), severity)
                setattr(self, f"{timepoint}_obs", results)

    def eval_triggers(self):
        triggers = dict()
        triggers['domain'] = dict()

        for domain in EMPRO_DOMAINS:
            if domain in self.cur_obs:
                dt = DomainTriggers(
                    domain=domain,
                    current_answers=self.cur_obs[domain],
                    previous_answers=self.prev_obs.get(domain),
                    initial_answers=self.initial_obs.get(domain)
                )
                triggers['domain'][domain] = dt.triggers

        return triggers
