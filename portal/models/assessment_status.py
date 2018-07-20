"""AssessmentStatus module"""
from collections import OrderedDict
from datetime import datetime

from flask import current_app

from ..dogpile_cache import dogpile_cache
from ..trace import trace
from .fhir import (
    CC,
    QuestionnaireResponse,
    qnr_document_id,
)
from .organization import OrgTree
from .questionnaire_bank import QuestionnaireBank
from .user import User
from .user_consent import UserConsent


def recent_qnr_status(user, questionnaire_name, qbd):
    """Look up recent status/timestamp for matching QuestionnaireResponse

    :param user: Patient to whom completed QuestionnaireResponses belong
    :param questionnaire_name: name of associated questionnaire
    :param qbd: QuestionnaireBank details for associated questionnaire
    :return: dictionary with authored (timestamp) of the most recent
        QuestionnaireResponse keyed by status found

    """
    query = QuestionnaireResponse.query.filter(
        QuestionnaireResponse.subject_id == user.id
    ).filter(
        QuestionnaireResponse.document[
            ('questionnaire', 'reference')
        ].astext.endswith(questionnaire_name),
        QuestionnaireResponse.questionnaire_bank_id == qbd.questionnaire_bank.id
    ).order_by(
        QuestionnaireResponse.status,
        QuestionnaireResponse.authored.desc()).with_entities(
        QuestionnaireResponse.status, QuestionnaireResponse.authored)

    if qbd.iteration is not None:
        query = query.filter(
            QuestionnaireResponse.qb_iteration == qbd.iteration)
    else:
        query = query.filter(QuestionnaireResponse.qb_iteration.is_(None))

    results = {}
    for qr in query:
        if qr[0] not in results:
            results[qr[0]] = qr[1]

    return results


def status_from_recents(recents, start, overdue, expired, as_of_date):
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
    as_of_date = as_of_date or datetime.utcnow()
    if as_of_date.date() < start.date():
        raise ValueError(
            "unexpected call for status on unstarted Questionnaire")

    if ((overdue and as_of_date < overdue) or
            (not overdue and as_of_date < expired)):
        tmp = {
            'status': 'Due',
            'by_date': overdue if overdue else expired
        }
        tmp.update(results)
        return tmp
    if overdue and as_of_date < expired:
        tmp = {
            'status': 'Overdue',
            'by_date': expired
        }
        tmp.update(results)
        return tmp
    tmp = {'status': 'Expired'}
    tmp.update(results)
    return tmp


def qb_status_dict(user, qbd, as_of_date):
    """Gather status details for a user on a given QBD"""
    d = OrderedDict()
    if not qbd.questionnaire_bank:
        return d
    trigger_date = qbd.questionnaire_bank.trigger_date(user)
    if not trigger_date:
        return d
    qbd_start = qbd.questionnaire_bank.calculated_start(
        trigger_date, as_of_date=as_of_date)
    # calculated_start does it's own lookup for iteration - should match
    if qbd_start.iteration != qbd.iteration:
        raise ValueError("iteration mismatch")
    start = qbd.relative_start
    if not start:
        raise ValueError("no start for {} {}, can't continue".format(
            user, qbd))
    overdue = qbd.questionnaire_bank.calculated_overdue(
        trigger_date, as_of_date=as_of_date)
    expired = qbd.questionnaire_bank.calculated_expiry(
        trigger_date, as_of_date=as_of_date)
    for q in qbd.questionnaire_bank.questionnaires:
        recents = recent_qnr_status(user, q.name, qbd)
        d[q.name] = status_from_recents(
            recents, start, overdue, expired, as_of_date=as_of_date)
    trace("QuestionnaireBank status for {}:".format(qbd))
    for k, v in d.items():
        trace("  {}:{}".format(k, v))
    return d


class QuestionnaireBankDetails(object):
    """Gather details on users most current QuestionnaireBank

    Houses details including questionnaire's classification, recent
    reports and details needed by clients like AssessmentStatus.

    """

    def __init__(self, user, as_of_date):
        """ Initialize and lookup status for respective questionnaires

        :param user: subject for details
        :param as_of_date: None value implies now

        """
        self.user = user
        self.qbd = QuestionnaireBank.most_current_qb(
            user, as_of_date=as_of_date)
        self.status_by_q = qb_status_dict(
            user=user, qbd=self.qbd, as_of_date=as_of_date)

    def completed_date(self):
        """Returns timestamp from most recent completed assessment"""
        dates = [
            self.status_by_q[q]['completed'] for q in self.status_by_q
            if 'completed' in self.status_by_q[q]]
        dates.sort(reverse=True)
        if dates:
            return dates[0]
        else:
            return None

    def overall_status(self):
        """Returns the `overall_status` for the given QB"""
        if self.withdrawn():
            return 'Withdrawn'

        if not (
                self.qbd.questionnaire_bank and
                self.qbd.questionnaire_bank.trigger_date
        ):
            return 'Expired'
        status_strings = [v['status'] for v in self.status_by_q.values()]
        if all((status_strings[0] == status for status in status_strings)):
            if not status_strings[0] in (
                    'Completed', 'Due', 'In Progress', 'Overdue',
                    'Expired'):
                raise ValueError('Unexpected common status {}'.format(
                    status_strings[0]))

            result = status_strings[0]

            # Edge case where all are in progress, but no time remains
            if status_strings[0] == 'In Progress':
                due_by = [
                    d.get('by_date') for d in self.status_by_q.values()]
                if not any(due_by):
                    result = 'Partially Completed'
        else:
            if any(('Expired' == status for status in status_strings)):
                result = 'Partially Completed'
            else:
                result = 'In Progress'
        return result

    def withdrawn(self):
        """Determine if user has `withdrawn` from study """
        # No easy tie between QB and organization.  Make assumption
        # that if the QBD isn't intervention tied, the user is associated
        # with the intervention by org.
        intervention_qbs = QuestionnaireBank.query.filter(
            QuestionnaireBank.intervention_id.isnot(None))
        if self.qbd.questionnaire_bank in intervention_qbs:
            return False

        # With multiple root organizations, the consent lookup would
        # be indeterminate - don't allow
        root_orgs = OrgTree().find_top_level_org(self.user.organizations)
        if len(root_orgs) > 1:
            current_app.logger.error(
                "Indeterminate org lookup - only expecting one root org "
                "for patient {}".format(self.user))

        valid_consent_found = False
        for candidate in self.user.organizations:
            if not candidate.id:  # `none of the above` doesn't count
                continue

            # Need to process in order, finding the consent closest to the
            # user's leaf org and then moving up.
            for org_id in OrgTree().at_and_above_ids(candidate.id):
                valid_consent = self.user.valid_consents.filter(
                    UserConsent.organization_id == org_id).with_entities(
                    UserConsent.options, UserConsent.status).first()
                if valid_consent:
                    valid_consent_found = True
                if valid_consent and valid_consent[1] == 'suspended':
                    return True

        if not valid_consent_found:
            current_app.logger.warn("No consent found for {}".format(self.user))
        return False


class AssessmentStatus(object):
    """Lookup and hold assessment status detail for a user

    Complicated task due to nature of multiple instruments which differ
    depending on user state such as localized or metastatic.

    """

    def __init__(self, user, as_of_date):
        """Initialize assessment status object for given user/consent

        :param user: The user in question - patient on whom to check status
        :param as_of_date: Use to override default of `now` for status calc

        """
        self.user = user
        self.as_of_date = as_of_date
        self.qb_data = QuestionnaireBankDetails(user, as_of_date=as_of_date)

    def __str__(self):
        """Present friendly format for logging, etc."""
        if self.qb_data.qbd.questionnaire_bank:
            iteration = (
                '' if self.qb_data.qbd.iteration is None
                else ", iteration {}".format(self.qb_data.qbd.iteration)
            )
            return (
                "{0.user} has overall status '{0.overall_status}' for "
                "QuestionnaireBank {0.qb_name}{1}".format(self, iteration))
        return "{0.user} has overall status '{0.overall_status}'".format(self)

    @property
    def completed_date(self):
        """Returns timestamp from most recent completed assessment"""
        return self.qb_data.completed_date()

    @property
    def localized(self):
        """Returns true if the user is known to have PCa_localized dx"""
        return self.user.concept_value(CC.PCaLocalized) == 'true'

    @property
    def __organization(self):
        """Returns the top organization associated with users's QB or None"""
        rp_id = self.qb_data.qbd.questionnaire_bank.research_protocol_id
        for org in self.user.organizations:
            org_rp = org.research_protocol(self.as_of_date)
            if org_rp and org_rp.id == rp_id:
                return OrgTree().find_top_level_org([org])[0]
        return None

    @property
    def assigning_authority(self):
        """Returns the best string available for the assigning authority

        Typically, the top-level organization used to associate the user
        with the questionnaire bank.  For organizations that have moved
        to a newer research protocol, we no longer have this lookup available.

        In this case, we're currently left to guessing - as the data model
        doesn't capture the authority (say organization or intervention)
        behind the assignment.  But given the typical scenario, the user will
        have one organization, and the top level of that will be the correct
        guess.

        If nothing is available, return an empty string as it can safely
        be used in string formatting.

        :returns: string for assigning authority or empty string

        """
        org = self.__organization or self.user.first_top_organization()
        return getattr(org, 'name', '')

    @property
    def qb_name(self):
        """Return name of applicable questionnaire bank if defined"""
        return getattr(self.qb_data.qbd.questionnaire_bank, 'name', None)

    def enrolled_in_classification(self, classification):
        """Returns true if user has at least one q for given classification"""
        return len(
            QuestionnaireBank.qbs_for_user(
                self.user, classification=classification,
                as_of_date=self.as_of_date)) > 0

    def _status_by_classification(self, classification):
        """Returns appropriate status dict for requested QB type(s)

        :raises ValueError: if classification other than None, 'all'
        or 'indefinite' - others not supported at this time.

        """
        if classification not in (None, 'all', 'indefinite'):
            raise ValueError("Unsupported stratification for status lookup")
        results = OrderedDict()
        if classification is None or classification == 'all':
            # Assumes current by default
            results = self.qb_data.status_by_q
        if classification in ('all', 'indefinite'):
            # Add indefinite as requested
            qbd = QuestionnaireBank.indefinite_qb(
                user=self.user, as_of_date=self.as_of_date)
            if qbd.questionnaire_bank:
                results.update(
                    qb_status_dict(self.user, qbd=qbd,
                                   as_of_date=self.as_of_date))
        return results

    def instruments_completed(self, classfication=None):
        """Return list of completed questionnaires"""
        results = [
            name for name, data in
            self._status_by_classification(classfication).items()
            if 'completed' in data]
        return results

    def instruments_needing_full_assessment(self, classification=None):
        """Return list of questionnaire names needed

        NB - if the questionnaire is outside the valid date range, such as in
        an expired state or prior to the next recurring cycle, it will not be
        included in the list regardless of its needing assessment status.

        :param classification: set to 'indefinite' to consider that
            classification, or 'all', otherwise uses current QB.
        :returns: list of questionnaire names (IDs)

        """
        results = []
        input = self._status_by_classification(classification)
        for name, data in input.items():
            if ('completed' in data or 'in-progress' in data or
                    data.get('status') == 'Expired'):
                continue
            results.append(name)
        return results

    def instruments_in_progress(self, classification=None):
        """Return list of questionnaire ids in-progress for classification

        NB - if the questionnaire is outside the valid date range, such as in
        an expired state, it will not be included in the list regardless of
        its in-progress status.

        :param classification: set to 'indefinite' to consider that
            classification, or 'all', otherwise uses current QB.
        :returns: list of external questionnaire identifiers, that is, the
            id needed to resume work on the same questionnaire that was
            in progress.  The `document['identifier']` from the previously
            submitted QuestionnaireResponse.

        """
        results = []
        input = self._status_by_classification(classification)
        for name, data in input.items():
            if 'in-progress' in data:
                # Only counts if there's a `by_date`, otherwise, although this
                # questionnaire is partially done, it can't be resumed
                if 'by_date' in data:
                    # Look up the external id and append to results
                    # Look out for indefinite work in-progress, as it
                    # belongs to a different questionnaire bank
                    qb_id = self.qb_data.qbd.questionnaire_bank.id
                    iteration = self.qb_data.qbd.iteration
                    if name not in (
                            q.name
                            for q in
                            self.qb_data.qbd.questionnaire_bank.questionnaires
                    ):
                        indef_qb = QuestionnaireBank.indefinite_qb(
                            user=self.user, as_of_date=self.as_of_date)
                        qb_id = indef_qb.questionnaire_bank.id
                        iteration = None  # indefinite doesn't recur

                    results.append(qnr_document_id(
                        subject_id=self.user.id,
                        questionnaire_bank_id=qb_id,
                        questionnaire_name=name,
                        iteration=iteration,
                        status='in-progress'))
        return results

    def next_available_due_date(self):
        """Lookup due_date from next available assessment

        Prefer due_date for first questionnaire needing full assessment, also
        consider those in process in case others don't qualify.

        :returns: due date of next available assessment, or None

        """
        for name, data in self.qb_data.status_by_q.items():
            if data.get('by_date'):
                return data.get('by_date')
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
            'Withdrawn': if the user's consent agreement with QB organization
                includes "send_reminders: False".

        """
        return self.qb_data.overall_status()


def invalidate_assessment_status_cache(user_id):
    """Invalidate the assessment status cache values for this user"""
    try:
        int(user_id)
    except:
        raise ValueError(
            "overall_assessment_status cached on user_id; int cast failed")
    dogpile_cache.invalidate(
        overall_assessment_status, user_id)


@dogpile_cache.region('hourly')
def overall_assessment_status(user_id):
    """Cachable interface for expensive assessment status lookup

    The following code is only run on a cache miss.

    """
    user = User.query.get(user_id)
    current_app.logger.debug("CACHE MISS: {} {}".format(
        __name__, user_id))
    now = datetime.utcnow()
    a_s = AssessmentStatus(user, as_of_date=now)
    qbd = QuestionnaireBank.most_current_qb(user, as_of_date=now)
    return (a_s.overall_status, qbd)
