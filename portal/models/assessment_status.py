"""AssessmentStatus module"""
from collections import OrderedDict
from datetime import datetime, timedelta
from flask import current_app

from ..dogpile import dogpile_cache
from .fhir import QuestionnaireResponse
from .organization import Organization, OrgTree
from .questionnaire_bank import QuestionnaireBank
from .user import User
from .user_consent import UserConsent


def most_recent_survey(user, instrument_id=None):
    """Look up timestamp for recent QuestionnaireResponse for user

    :param user: Patient to whom completed QuestionnaireResponses belong
    :param instrument_id: Optional parameter to limit type of
        QuestionnaireResponse in lookup.
    :return: dictionary with authored (timestamp) of the most recent
        QuestionnaireResponse keyed by status found

    """
    query = QuestionnaireResponse.query.distinct(
        QuestionnaireResponse.status).filter(
            QuestionnaireResponse.subject_id == user.id)
    if instrument_id:
        query = query.filter(
            QuestionnaireResponse.document[
                ('questionnaire', 'reference')
            ].astext.endswith(instrument_id))
    query = query.order_by(
        QuestionnaireResponse.status,
        QuestionnaireResponse.authored).limit(9).with_entities(
            QuestionnaireResponse.status, QuestionnaireResponse.authored)
    results = {}
    for qr in query:
        if qr[0] not in results:
            results[qr[0]] = qr[1]

    return results


def qbs_for_user(user, classification):
    """Return questionnaire banks for the given (user, classification)

    QuestionnaireBanks are associated with a user through the top
    level organization affiliation.

    :return: matching QuestionnaireBanks if found, else empty list

    """
    results = []
    for org in (o for o in user.organizations if o.id):
        top = OrgTree().find(org.id).top_level()
        qbs = QuestionnaireBank.query.filter(
            QuestionnaireBank.organization_id == top,
            QuestionnaireBank.classification == classification).all()
        if qbs:
            results.extend(qbs)

    def validate_classification_count(qbs):
        if len(qbs) > 1:
            current_app.logger.error(
                "multiple QuestionnaireBanks for {user} with "
                "{classification} found.  The UI won't correctly display "
                "more than one at this time.".format(
                    user=user, classification=classification))

    validate_classification_count(results)
    return results


class QuestionnaireDetails(object):
    """Encapsulate details needed for a questionnaire

    Houses details including questionnaire's classification, recent
    reports and details needed by clients like AssessmentStatus.
    """

    def __init__(self, user, consent_date):
        self.user = user
        self.consent_date = consent_date
        self._baseline_qs = OrderedDict()
        self._recurring_qs = OrderedDict()
        self._indefinite_qs = OrderedDict()
        for classification in ('baseline', 'recurring', 'indefinite'):
            for qb in qbs_for_user(user, classification):
                for questionnaire in qb.questionnaires:
                    self._append_questionnaire(
                        classification=classification,
                        questionnaire=questionnaire,
                        organization_id=qb.organization_id)

    def lookup(self, questionnaire_name, classification):
        """Return element (if found) with matching criteria"""
        if classification == 'all':
            raise NotImplementedError(
                "`lookup' not yet supporting `all` classifications")
        storage = getattr(self, '_{}_qs'.format(classification))
        if not storage:
            raise ValueError("unknown classification: {}".format(
                classification))
        return storage.get(questionnaire_name)

    def all(self):
        """Generator to return all questionnaires"""
        for q in (
                self._baseline_qs.values() +
                self._recurring_qs.values() +
                self._indefinite_qs.values()):
            yield q

    def baseline(self):
        """Generator to return all baseline questionnaires"""
        for q in self._baseline_qs.values():
            yield q

    def indefinite(self):
        """Generator to return all indefinite questionnaires"""
        for q in self._indefinite_qs.values():
            yield q

    def recurring(self):
        """Generator to return all recurring questionnaires"""
        for q in self._recurring_qs.values():
            yield q

    def _append_questionnaire(self, classification, questionnaire,
                              organization_id):
        """Build up internal ordered dict from given values"""
        storage = getattr(self, '_{}_qs'.format(classification))
        if questionnaire.name in storage:
            raise ValueError(
                "questionnaires expected to be unique by classification, "
                "{} already defined for {}".format(
                    questionnaire.name, classification))

        def status_from_recents(
                recents, days_till_due, days_till_overdue, start):
            """Returns dict defining available values from recents

            Return dict will only define values which make sense.  i.e.
            'completed' is only present if status is 'Completed', and
            'by_date' is only present if it's not completed or expired.

            """
            results = {}
            if 'completed' in recents:
                return {
                    'status': 'Completed',
                    'completed': recents['completed']
                }
            if 'in-progress' in recents:
                results['status'] = 'In Progress'
                results['in-progress'] = recents['in-progress']
            today = datetime.utcnow()
            delta = today - start
            if delta < timedelta(days=days_till_due):
                tmp = {
                    'status': 'Due',
                    'by_date': (
                        start + timedelta(days=days_till_due))
                   }
                tmp.update(results)
                return tmp
            if delta < timedelta(days=days_till_overdue):
                tmp = {
                    'status': 'Overdue',
                    'by_date': start + timedelta(
                        days=days_till_overdue)
                   }
                tmp.update(results)
                return tmp
            tmp = {'status': 'Expired'}
            tmp.update(results)
            return tmp

        def questionnaire_start_date(questionnaire):
            """Return relative start date for questionnare or None

            Determine if questionnaire qualifies for inclusion, if not, return
            None.  If it qualifies, return the start date.  Typically this is
            the consent_date except on recurring questionnaries, where it's
            the effective start_date for the active recurrance cycle.

            :return: datetime of the questionnaire's start date; None if N/A

            """
            if len(questionnaire.recurs):
                for recurrance in questionnaire.recurs:
                    relative_start = recurrance.active_interval_start(
                        start=self.consent_date)
                    if relative_start:
                        return relative_start
                return None  # no active recurrance
            return self.consent_date

        relative_start = questionnaire_start_date(questionnaire)
        if not relative_start:
            return

        storage[questionnaire.name] = {
            'name': questionnaire.name,
            'classification': classification,
            'organization_id': organization_id
        }
        storage[questionnaire.name].update(
            status_from_recents(recents=most_recent_survey(
                self.user, questionnaire.name),
                days_till_due=questionnaire.days_till_due,
                days_till_overdue=questionnaire.days_till_overdue,
                start=relative_start))


class AssessmentStatus(object):
    """Lookup and hold assessment status detail for a user

    Complicated task due to nature of multiple instruments which differ
    depending on user state such as localized or metastatic.

    """

    def __init__(self, user, consent=None):
        """Initialize assessment status object for given user/consent

        :param user: The user in question - patient on whom to check status
        :param consent: Consent agreement defining dates and which organization
            to consider in the status check.  If not provided, use the first
            valid consent found for the user.  Users w/o consents have
            overall_status of `Expired`

        """
        self.user = user
        self._consent = consent
        self.questionnaire_data = QuestionnaireDetails(user, self.consent_date)

    def __str__(self):
        """Present friendly format for logging, etc."""
        results = (
            "{0.user} has overall status '{0.overall_status}' for "
            "baseline questionnaires:".format(self))

        return results + str(
            ['{}:{}'.format(unicode(q['name']), unicode(q['status']))
             for q in self.questionnaire_data.baseline()])

    @property
    def consent_date(self):
        """Return timestamp of signed consent, if available, else None"""
        if hasattr(self, '_consent_date'):
            return self._consent_date
        else:
            if not self._consent:
                if self.user.valid_consents and len(list(
                        self.user.valid_consents)) > 0:
                    self._consent = self.user.valid_consents[0]
            if self._consent:
                self._consent_date = self._consent.audit.timestamp
            else:
                self._consent_date = None
            return self._consent_date

    @property
    def completed_date(self):
        """Returns timestamp from most recent completed assessment"""
        dates = [
            q['completed'] for q in self.questionnaire_data.all()
            if 'completed' in q]
        dates.sort(reverse=True)
        if dates:
            return dates[0]
        else:
            return None

    @property
    def localized(self):
        """Returns true if the user is associated with the localized org"""
        local_org = current_app.config.get('LOCALIZED_AFFILIATE_ORG', None)
        if local_org in self.user.organizations:
            return True
        else:
            return False

    @property
    def organization(self):
        """Returns the organization associated with users's baseline"""
        first_baseline = next(self.questionnaire_data.baseline(), None)
        if first_baseline:
            return Organization.query.get(first_baseline['organization_id'])
        else:
            return

    def enrolled_in_classification(self, classification):
        """Returns true if user has at least one q for given classification"""
        filter = getattr(self.questionnaire_data, classification)
        for one in filter():
            return True
        return False

    def instruments_needing_full_assessment(self, classification):
        """Return list of questionnaire names needed for classification

        NB - if the questionnaire is outside the valid date range, such as in
        an expired state or prior to the next recurring cycle, it will not be
        included in the list regardless of its needing assessment status.

        :param classification: set to restrict lookup to a single
            QuestionnaireBank.classification or 'all' to consider all.
        :returns: list of questionnaire names (IDs)

        """
        filter = getattr(self.questionnaire_data, classification)
        results = []
        for data in filter():
            if ('completed' in data or 'in-progress' in data or
                    data.get('status') == 'Expired'):
                continue
            results.append(data['name'])

        return results

    def instruments_in_progress(self, classification):
        """Return list of questionnaire names in-progress for classification

        NB - if the questionnaire is outside the valid date range, such as in
        an expired state, it will not be included in the list regardless of
        its in-progress status.

        :param classification: set to restrict lookup to a single
            QuestionnaireBank.classification or 'all' to consider all.
        :returns: list of questionnaire names (IDs)

        """
        filter = getattr(self.questionnaire_data, classification)
        results = []
        for data in filter():
            if 'in-progress' in data:
                # Only counts if there's a `by_date`, otherwise, although this
                # questionnaire is partially done, it can't be resumed
                if 'by_date' in data:
                    results.append(data['name'])

        return results

    def next_available_due_date(self, classification):
        """Lookup due_date from next available assessment for classification

        Considering the classification, prefer due_date for first
        questionnaire needing full assessment, also consider those in
        process in case others don't qualify.

        :param classification: set to restrict lookup to a single
            QuestionnaireBank.classification or 'all' to consider all.
        :returns: due date of next available assessment, or None

        """
        instruments = (
            self.instruments_needing_full_assessment(classification)
            or self.instruments_in_progress(classification))
        for i in instruments:
            due_date = self.questionnaire_data.lookup(
                questionnaire_name=i, classification=classification).get(
                    'by_date')
            if due_date:
                return due_date

        return None

    @property
    def overall_status(self):
        """Returns display quality string for user's overall status

        returns:
            'Completed': if all questionnaires in the bank were completed.
            'Due': if all questionnaires are unstarted and the days since
                consenting hasn't exceeded the 'days_till_due' for all
                questionnaires.
            'Expired': if we don't have a consent date for the user, or
                if there are no questionnaires assigned to the user, or
                if all questionnaires in the bank have expired.
            'Overdue': if all questionnaires are unstarted and the days since
                consenting hasn't exceeded the 'days_till_overdue' for all
                questionnaires.  (NB - check for 'due' runs first)
            'Partially Completed': if one or more questionnaires were at least
                started and at least one questionnaire is expired.
            'In Progress': if one or more questionnaires were at least
                started and the remaining unfinished questionnaires are not
                expired.

        """
        if hasattr(self, '_overall_status'):
            return self._overall_status
        else:
            first_baseline = next(self.questionnaire_data.baseline(), None)
            if not self.consent_date or not first_baseline:
                self._overall_status = 'Expired'
                return self._overall_status
            status_strings = [
                details['status'] for details in
                self.questionnaire_data.baseline()]
            if all((status_strings[0] == status for status in status_strings)):
                if not status_strings[0] in (
                        'Completed', 'Due', 'In Progress', 'Overdue',
                        'Expired'):
                    raise ValueError('Unexpected common status {}'.format(
                        status_strings[0]))

                self._overall_status = status_strings[0]

                # Edge case where all are in progress, but no time remains
                if status_strings[0] == 'In Progress':
                    due_by = [
                        d.get('by_date') for d in
                        self.questionnaire_data.baseline()]
                    if not any(due_by):
                        self._overall_status = 'Partially Completed'
            else:
                if any(('Expired' == status for status in status_strings)):
                    self._overall_status = 'Partially Completed'
                else:
                    self._overall_status = 'In Progress'
            return self._overall_status


@dogpile_cache.region('hourly')
def overall_assessment_status(user_id, consent_id=None):
    """Cachable interface for expensive assessment status lookup

    The following code is only run on a cache miss.

    """
    user = User.query.get(user_id)
    consent = UserConsent.query.get(consent_id) if consent_id else None
    current_app.logger.debug("CACHE MISS: {} {} {}".format(
        __name__, user_id, consent_id))
    a_s = AssessmentStatus(user, consent)
    return a_s.overall_status
