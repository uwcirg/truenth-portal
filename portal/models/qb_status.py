""" Questionnaire Bank Status Module

API to lookup user's status with respect to assigned questionnaire banks.

"""
from .overall_status import OverallStatus
from .qb_timeline import ordered_qbs, QBT, update_users_QBT
from .questionnaire_response import qnr_document_id, QNR_results
from ..trace import trace


class NoCurrentQB(Exception):
    """Exception to raise when no current QB is available yet required"""
    pass


class QB_Status(object):

    def __init__(self, user, as_of_date):
        self.user = user
        self.as_of_date = as_of_date
        for state in OverallStatus:
            setattr(self, "_{}_date".format(state.name), None)
        self._overall_status = None
        self._sync_timeline()
        self._indef_stats()

    def _sync_timeline(self):
        """Sync QB timeline and obtain status"""
        self.prev_qbd, self.next_qbd = None, None

        # Update QB_Timeline for user, if necessary
        update_users_QBT(self.user.id)

        # Every QB should have "due" - filter by to get one per QB
        users_qbs = QBT.query.filter(QBT.user_id == self.user.id).filter(
            QBT.status == OverallStatus.due).order_by(QBT.at.asc())

        # convert query to list of tuples for easier manipulation
        self.__ordered_qbs = [qbt.qbd() for qbt in users_qbs]
        if not self.__ordered_qbs:
            # Look for withdrawn case
            if QBT.query.filter(QBT.user_id == self.user.id).filter(
                    QBT.status == OverallStatus.withdrawn).count():
                self._overall_status = OverallStatus.withdrawn
                trace("found user withdrawn")
            else:
                self._overall_status = OverallStatus.expired
                trace("no qb timeline data for {}".format(self.user))
            self._enrolled_in_common = False
            self._current = None
            return
        self._enrolled_in_common = True

        # locate current qb - last found with start <= now
        cur_index, cur_qbd = None, None
        for i, qbd in zip(range(len(self.__ordered_qbs)), self.__ordered_qbs):
            if qbd.relative_start <= self.as_of_date:
                cur_index = i
                cur_qbd = qbd
            if qbd.relative_start > self.as_of_date:
                break

        # w/o a cur, probably hasn't started, set expired and leave
        if not cur_qbd and (
                self.__ordered_qbs[0].relative_start > self.as_of_date):
            trace(
                "no current QBD (too early); first qb doesn't start till"
                " {} vs as_of {}".format(
                    self.__ordered_qbs[0].relative_start, self.as_of_date))
            self._overall_status = OverallStatus.expired
            self._current = None
            self.next_qbd = self.__ordered_qbs[0]
            return

        if cur_index > 0:
            self.prev_qbd = self.__ordered_qbs[cur_index-1]
        else:
            self.prev_qbd = None

        if cur_index < len(self.__ordered_qbs) - 1:
            self.next_qbd = self.__ordered_qbs[cur_index+1]
        else:
            self.next_qbd = None

        self._status_from_current(cur_qbd)

    def _status_from_current(self, cur_qbd):
        """Obtain status from QB timeline given current QBD"""
        cur_rows = QBT.query.filter(QBT.user_id == self.user.id).filter(
            QBT.qb_id == cur_qbd.qb_id).filter(
            QBT.qb_recur_id == cur_qbd.recur_id).filter(
            QBT.qb_iteration == cur_qbd.iteration).order_by(QBT.at)

        # whip through ordered rows picking up available status
        for row in cur_rows:
            if row.at <= self.as_of_date:
                self._overall_status = row.status

            if row.status == OverallStatus.due:
                self._due_date = row.at
            if row.status == OverallStatus.overdue:
                self._overdue_date = row.at
            if row.status == OverallStatus.completed:
                self._completed_date = row.at
            if row.status == OverallStatus.in_progress:
                self._in_progress_date = row.at
                # If we didn't already pass the overdue date, obtain now
                if not self._overdue_date and self._due_date:
                    self._overdue_date = (
                        cur_qbd.questionnaire_bank.calculated_overdue(
                            self._due_date))
            if row.status in (
                    OverallStatus.expired,
                    OverallStatus.partially_completed):
                self._expired_date = row.at

        # If the current is already expired, then no current was found,
        # as current is actually the previous
        if self._expired_date and self._expired_date < self.as_of_date:
            self.prev_qbd = cur_qbd
            self._current = None
        else:
            self._current = cur_qbd

    def older_qbds(self, last_known):
        """Generator to return QBDs and status prior to last known

        Expected use in reporting scenarios, where full history is needed,
        this generator will continue to return previous QBDs (from last_known)
        until exhausted.

        :param last_known: typically a valid QBD for the user, typically the
          ``current_qbd()`` or possibly the previous.  None safe
        :returns: (QBD, status) until exhausted, then raises StopIteration

        """
        if last_known is None:
            raise StopIteration

        index = self.__ordered_qbs.index(last_known)
        while index > 0:
            index -= 1
            cur_qbd = self.__ordered_qbs[index]
            # We order by at (to get the latest status for a given QB) and
            # secondly by id, as on rare occasions, the time (`at`) of
            #  `due` == `completed`, but the row insertion defines priority
            status = QBT.query.filter(QBT.user_id == self.user.id).filter(
                QBT.qb_id == cur_qbd.qb_id).filter(
                QBT.qb_recur_id == cur_qbd.recur_id).filter(
                QBT.qb_iteration == cur_qbd.iteration).order_by(
                QBT.at.desc(), QBT.id.desc()).with_entities(
                QBT.status).first()
            yield self.__ordered_qbs[index], str(status[0])

    def _indef_stats(self):
        """Lookup stats for indefinite case - requires special handling"""
        qbs = ordered_qbs(self.user, classification='indefinite')
        self._current_indef = None
        for q in qbs:
            if self._current_indef is not None:
                raise RuntimeError("unexpected second indef qb")
            self._current_indef = q

    def _response_lookup(self):
        """Lazy init - only lookup associated QNRs if needed"""
        if hasattr(self, '_responses_looked_up'):
            return

        # As order counts, required is a list; partial and completed are sets
        if self._current:
            user_qnrs = QNR_results(
                self.user, qb_id=self._current.qb_id,
                qb_iteration=self._current.iteration)
            self._required = user_qnrs.required_qs(self._current.qb_id)
            self._partial = user_qnrs.partial_qs(
                qb_id=self._current.qb_id, iteration=self._current.iteration)
            self._completed = user_qnrs.completed_qs(
                qb_id=self._current.qb_id, iteration=self._current.iteration)

        # Indefinite is similar, but *special*
        if self._current_indef:
            user_indef_qnrs = QNR_results(
                self.user, qb_id=self._current_indef.qb_id)
            self._required_indef = user_indef_qnrs.required_qs(
                qb_id=self._current_indef.qb_id)
            self._partial_indef = user_indef_qnrs.partial_qs(
                qb_id=self._current_indef.qb_id, iteration=None)
            self._completed_indef = user_indef_qnrs.completed_qs(
                qb_id=self._current_indef.qb_id, iteration=None)

        self._responses_looked_up = True

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
        org = self.user.first_top_organization()
        return getattr(org, 'name', '')

    def current_qbd(self, classification=None):
        """ Looks for current QBD for given parameters

        If the user has a valid questionnaire bank for the given as_of_date
        and classification, return the matching QuestionnaireBankDetails
        (QBD), which fully defines the questionnaire bank, iteration, recur
        and start date.

        :param as_of_date: point in time for reference, frequently utcnow
        :param classification: None defaults to all, special case for
          ``indefinite``
        :return: QBD for best match, on None

        """
        if classification == 'indefinite':
            return self._current_indef
        if self._current:
            self._current.relative_start = self._due_date
        return self._current

    @property
    def overall_status(self):
        return self._overall_status

    @property
    def completed_date(self):
        return self._completed_date

    @property
    def due_date(self):
        return self._due_date

    @property
    def expired_date(self):
        return self._expired_date

    @property
    def overdue_date(self):
        return self._overdue_date

    def __instruments_by_strategy(self, classification, strategy):
        """Common logic for differing strategy to obtain instrument lists

        Given a strategy function, returns the appropriate list.
        """
        if classification not in (None, 'all', 'indefinite'):
            raise ValueError("can't handle classification {}".format(
                classification))

        self._response_lookup()  # force lazy load if not done

        results = []

        if classification in ('all', None) and self._current:
            results = strategy(
                required_list=self._required,
                completed_set=self._completed,
                partial_set=self._partial)

        if classification in ('indefinite', 'all') and self._current_indef:
            results += strategy(
                required_list=self._required_indef,
                completed_set=self._completed_indef,
                partial_set=self._partial_indef)

        return results

    def instruments_needing_full_assessment(self, classification=None):

        def needing_full(required_list, completed_set, partial_set):
            # maintain order from required list, include all not
            # stared nor completed
            return [
                i for i in required_list if i not in completed_set
                and i not in partial_set]

        return self.__instruments_by_strategy(classification, needing_full)

    def instruments_completed(self, classification=None):

        def completed(required_list, completed_set, partial_set):
            # maintain order from required list, include only if completed
            return [
                i for i in required_list if i in completed_set]

        return self.__instruments_by_strategy(classification, completed)

    def instruments_in_progress(self, classification=None):
        """Return list of questionnaire ids in-progress for classification

        NB - if the questionnaire is outside the valid date range, such as in
        an expired state, it will not be included in the list regardless of
        its in-progress status.

        :param classification: set to 'indefinite' to consider that
           classification, or 'all' for both.  Default None uses current.
        :returns: list of external questionnaire identifiers, that is, the
           id needed to resume work on the same questionnaire that was
           in progress.  The `document['identifier']` from the previously
           submitted QuestionnaireResponse.

       """
        def need_completion(required_list, completed_set, partial_set):
            # maintain order from required list, include if started (partial)
            # and not completed
            return [
                i for i in required_list if i not in completed_set
                and i in partial_set]

        in_progress = self.__instruments_by_strategy(
            classification, need_completion)

        def doc_id_lookup(instrument):
            """Obtain lookup keys from appropriate internals"""
            # don't have instrument to qb association at this
            # point, expect it belongs to one of the current!
            qb_id = None
            if self._current:
                qb = self._current.questionnaire_bank
                if instrument in [q.name for q in qb.questionnaires]:
                    qb_id = qb.id
                    iteration = self._current.iteration
            if not qb_id and self._current_indef:
                qb = self._current_indef.questionnaire_bank
                if instrument not in [q.name for q in qb.questionnaires]:
                    raise ValueError(
                        "Can't locate qb containing {} for continuation "
                        "session (doc_id) lookup".format(instrument))
                qb_id = qb.id
                iteration = self._current_indef.iteration

            return qnr_document_id(
                subject_id=self.user.id,
                questionnaire_bank_id=qb_id,
                questionnaire_name=instrument,
                iteration=iteration,
                status='in-progress')

        # Lookup document id to resume session on correct document
        results = []
        for i in in_progress:
            results.append(doc_id_lookup(i))
        return results

    def enrolled_in_classification(self, classification):
        """Returns true if user has at least one q for given classification"""
        if classification not in ('baseline', 'all', 'indefinite'):
            raise ValueError(
                "Unsupported classification '{}' for status lookup".format(
                    classification))

        if classification == 'indefinite':
            return self._current_indef
        elif classification == 'baseline':
            return self._enrolled_in_common
        else:
            return self._enrolled_in_common and self._current_indef
