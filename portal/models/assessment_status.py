"""AssessmentStatus module"""
from collections import OrderedDict
from datetime import datetime, timedelta
from flask import current_app

from .fhir import QuestionnaireResponse
from .questionnaire_bank import QuestionnaireBank


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
                ("questionnaire", "reference")
            ].astext.endswith(instrument_id))

    query = query.order_by(
        QuestionnaireResponse.status,
        QuestionnaireResponse.authored).limit(
            5).with_entities(QuestionnaireResponse.status,
                            QuestionnaireResponse.authored)
    results = {}
    for qr in query:
        if qr[1] not in results:
            results[qr[0]] = qr[1]
    return results



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
        self._overall_status, self._consent_date = None, None
        #self._localized = localized_PCa(user)
        self.instrument_status = OrderedDict()

    @property
    def consent_date(self):
        """Return timestamp of signed consent, if available, else None"""

        if self._consent_date:
            return self._consent_date

        # If we aren't given a consent, use the first valid consent found
        # for the user.
        if not self._consent:
            if self.user.valid_consents and len(list(self.user.valid_consents)) > 0:
                self._consent = self.user.valid_consents[0]

        if self._consent:
            self._consent_date = self._consent.audit.timestamp
        else:
            # Tempting to call this invalid state, but it's possible
            # the consent has been revoked, treat as expired.
            self._consent_date = None
        return self._consent_date

    @property
    def completed_date(self):
        """Returns timestamp from completed assessment, if available"""
        self.__obtain_status_details()
        best_date = None
        for instrument, details in self.instrument_status.items():
            if 'completed' in details:
                # TODO: in event of multiple completed instruments,
                # not sure *which* date is best??
                best_date = details['completed']
        return best_date

    @property
    def localized(self):
        """Returns true if the user is associated with the localized org"""
        local_org = current_app.config.get('LOCALIZED_AFFILIATE_ORG', None)
        if local_org in self.user.organizations:
            return True
        return False

    @property
    def overall_status(self):
        """Returns display quality string for user's overall status"""
        self.__obtain_status_details()
        return self._overall_status

    def instruments_needing_full_assessment(self):
        self.__obtain_status_details()
        results = []
        for instrument_id, details in self.instrument_status.items():
            if 'completed' in details or 'in-progress' in details:
                continue
            results.append(instrument_id)
        return results

    def instruments_in_process(self):
        self.__obtain_status_details()
        results = []
        for instrument_id, details in self.instrument_status.items():
            if 'in-progress' in details:
                results.append(instrument_id)
        return results

    def next_available_due_date(self):
        """Lookup due_date from next available assessment

        Prefer due_date for first instrument needing full assessment,
        also consider those in process in case others don't qualify.

        :returns: due date of next available assessment, or None

        """
        result = None
        instruments = (
            self.instruments_needing_full_assessment() or
            self.instruments_in_process()
        )
        due_dates = [self.instrument_status[i].get(
            'by_date') for i in instruments]

        # return first non-none
        try:
            result = next(dd for dd in due_dates if dd is not None)
        except StopIteration:
            pass  # happens if every item in due_dates is None
        return result

    def __obtain_status_details(self):
        # expensive process - do once
        if hasattr(self, '_details_obtained'):
            return
        if not self.consent_date:
            self._overall_status = 'Expired'
            self._details_obtained = True
            return

        # instrument/questionnaire list comes from the QuestionnaireBank
        # associated with this user
        questionnaires = QuestionnaireBank.q_for_user(self.user)
        if not questionnaires:
            self._overall_status = 'Not Enrolled'
            self._details_obtained = True
            return

        for q in questionnaires:
            self.__status_per_instrument(
                q.name, q.days_till_due, q.days_till_overdue)

        status_strings = [details['status'] for details in
                          self.instrument_status.values()]

        if all(status_strings[0] == status for status in status_strings):
            # All intruments in the same state - use the common value
            self._overall_status = status_strings[0]
        else:
            if any("Expired" == status for status in status_strings):
                # At least one expired, but not all
                self._overall_status = "Partially Completed"
            self._overall_status = "In Progress"
        self._details_obtained = True

    def __status_per_instrument(
        self, instrument_id, days_till_due, days_till_overdue):
        """Returns status for one instrument

        :param instrument_id: the instument in question
        :param days_till_due: integer value for end period of 'due'
        :param days_till_overdue: integer day count for end of 'overdue'
        :return: matching status string from constraints

        """
        def status_from_recents(recents):
            """Returns tuple ('status string', by_date) from recents

            NB - by_date only makes sense for some states, None otherwise

            """
            if 'completed' in recents:
                return ("Completed", None)
            status = None
            if 'in-progress' in recents:
                status = "In Progress"
            today = datetime.utcnow()
            delta = today - self.consent_date
            if delta < timedelta(days=days_till_due+1):
                status = status or "Due"
                return (status,
                        self.consent_date + timedelta(days=days_till_due))
            if delta < timedelta(days=days_till_overdue+1):
                status = status or "Overdue"
                return (status,
                        self.consent_date + timedelta(days=days_till_overdue))
            return ("Expired", None)

        if not instrument_id in self.instrument_status:
            self.instrument_status[instrument_id] = most_recent_survey(
                self.user, instrument_id)
        if not 'status' in self.instrument_status[instrument_id]:
            (self.instrument_status[instrument_id]['status'],
             self.instrument_status[instrument_id]['by_date']) =\
                    status_from_recents(self.instrument_status[instrument_id])
