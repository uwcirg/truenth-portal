""" Questionnaire Bank Status Module

API to lookup user's status with respect to assigned questionnaire banks.

"""
from flask import current_app
from ..trace import trace
from .overall_status import OverallStatus
from .qb_timeline import QBT, ordered_qbs, update_users_QBT
from .questionnaire_response import (
    QNR_indef_results,
    QNR_results,
    qnr_document_id,
)


class NoCurrentQB(Exception):
    """Exception to raise when no current QB is available yet required"""
    pass


class QB_Status(object):

    def __init__(self, user, research_study_id, as_of_date):
        self.user = user
        self.as_of_date = as_of_date
        self.research_study_id = research_study_id
        for state in OverallStatus:
            setattr(self, "_{}_date".format(state.name), None)
        self._target_date = None
        self._overall_status = None
        self._enrolled_in_common = False
        self._current = None
        self._sync_timeline()
        self._indef_init()

    def _sync_timeline(self):
        """Sync QB timeline and obtain status"""
        self.prev_qbd, self.next_qbd = None, None

        # Update QB_Timeline for user, if necessary
        update_users_QBT(self.user.id, self.research_study_id)

        # Every QB should have "due" - filter by to get one per QB
        users_qbs = QBT.query.filter(QBT.user_id == self.user.id).filter(
            QBT.research_study_id == self.research_study_id).filter(
            QBT.status == OverallStatus.due).order_by(QBT.at.asc())

        # Obtain withdrawal date if applicable
        withdrawn = QBT.query.filter(QBT.user_id == self.user.id).filter(
            QBT.research_study_id == self.research_study_id).filter(
            QBT.status == OverallStatus.withdrawn).first()
        self._withdrawal_date = withdrawn.at if withdrawn else None
        if self.withdrawn_by(self.as_of_date):
            self._overall_status = OverallStatus.withdrawn
            trace("found user withdrawn")

        # convert query to list of tuples for easier manipulation
        self.__ordered_qbs = [qbt.qbd() for qbt in users_qbs]
        if not self.__ordered_qbs:
            # May have withdrawn prior to first qb
            if self._withdrawal_date:
                self._overall_status = OverallStatus.withdrawn
                trace("found user withdrawn prior to start; no valid qbs")
            else:
                self._overall_status = OverallStatus.expired
                trace("no qb timeline data for {}".format(self.user))
            return
        self._enrolled_in_common = True

        # locate current qb - last found with start <= self.as_of_date
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
        # We order by at (to get the latest status for a given QB) and
        # secondly by id, as on rare occasions, the time (`at`) of
        #  `due` == `completed`, but the row insertion defines priority
        cur_rows = QBT.query.filter(QBT.user_id == self.user.id).filter(
            QBT.qb_id == cur_qbd.qb_id).filter(
            QBT.qb_recur_id == cur_qbd.recur_id).filter(
            QBT.qb_iteration == cur_qbd.iteration).order_by(
            QBT.at, QBT.id)

        # If the user has withdrawn, don't update status beyond the user's
        # withdrawal date.
        fencepost = (
            self._withdrawal_date if self.withdrawn_by(self.as_of_date)
            else self.as_of_date)

        # whip through ordered rows picking up available status
        for row in cur_rows:
            if row.at <= fencepost:
                self._overall_status = row.status

            if row.status == OverallStatus.due:
                self._due_date = row.at
                # HACK to manage target date until due means due (not start)
                self._target_date = cur_qbd.questionnaire_bank.calculated_due(
                    self._due_date)

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

        # Withdrawn sanity check
        if self.withdrawn_by(self.as_of_date) and (
                self.overall_status != OverallStatus.withdrawn):
            current_app.logger.error(
                "Unexpected state %s, user %d should be withdrawn",
                self.overall_status, self.user.id)

    def older_qbds(self, last_known):
        """Generator to return QBDs and status prior to last known

        Expected use in reporting scenarios, where full history is needed,
        this generator will continue to return previous QBDs (from last_known)
        until exhausted.

        :param last_known: typically a valid QBD for the user, typically the
          ``current_qbd()`` or possibly the previous.  None safe
        :returns: (QBD, status) until exhausted

        """
        if last_known is None:
            return

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
            # production errors seen, where qb_timeline loses data.  likely
            # a race condition where adherence cache is using timeline rows
            # when another thread purges the user's timeline.  log and exit
            if status is None:
                current_app.logger.info(
                    f"timeline data disappeared mid loop {self.user.id}: {QBT}")
                return
            yield self.__ordered_qbs[index], str(status[0])

    def _indef_init(self):
        """Lookup stats for indefinite case - requires special handling"""
        qbs = ordered_qbs(
            self.user, research_study_id=self.research_study_id,
            classification='indefinite')
        self._current_indef = None
        for q in qbs:
            if self._current_indef is not None:
                raise RuntimeError("unexpected second indef qb")
            if q.relative_start > self.as_of_date:
                # Don't include if the consent date hasn't arrived
                continue
            self._current_indef = q

    def indef_status(self):
        """Return indef QBD and status"""
        if not self.enrolled_in_classification(classification='indefinite'):
            return None, None

        qbd = next(ordered_qbs(
            self.user,
            research_study_id=self.research_study_id,
            classification='indefinite'))
        self._response_lookup()
        if self.overall_status == OverallStatus.withdrawn:
            status = OverallStatus.withdrawn
            # Special circumstance for completed/partial withdrawn (TN-3014)
            if self._partial_indef:
                status = OverallStatus.partially_completed
            if self._completed_indef.issuperset(self._required_indef):
                status = OverallStatus.completed

        elif self._partial_indef:
            status = OverallStatus.in_progress
        elif self._completed_indef.issuperset(self._required_indef):
            status = OverallStatus.completed
        elif self._required_indef:
            status = OverallStatus.due
        return qbd, str(status)

    def _response_lookup(self):
        """Lazy init - only lookup associated QNRs if needed"""
        if hasattr(self, '_responses_looked_up'):
            return

        # As order counts, required is a list; partial and completed are sets
        if self._current:
            user_qnrs = QNR_results(
                self.user,
                research_study_id=self.research_study_id,
                qb_ids=[self._current.qb_id],
                qb_iteration=self._current.iteration)
            self._required = user_qnrs.required_qs(self._current.qb_id)
            self._partial = user_qnrs.partial_qs(
                qb_id=self._current.qb_id, iteration=self._current.iteration)
            self._completed = user_qnrs.completed_qs(
                qb_id=self._current.qb_id, iteration=self._current.iteration)

        # Indefinite is similar, but *special*
        if self._current_indef:
            user_indef_qnrs = QNR_indef_results(
                self.user,
                research_study_id=self.research_study_id,
                qb_id=self._current_indef.qb_id)
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

    def current_qbd(self, classification=None, even_if_withdrawn=False):
        """ Looks for current QBD for given parameters

        If the user has a valid questionnaire bank for the given as_of_date
        and classification, return the matching QuestionnaireBankDetails
        (QBD), which fully defines the questionnaire bank, iteration, recur
        and start date.

        :param classification: None defaults to all, special case for
          ``indefinite``
        :param even_if_withdrawn: Set true to get the current, even if the
          patient may be in a withdrawn state.  By default, post the withdrawal
          date, a patient doesn't have a current QBD.
        :return: QBD for best match, or None

        """
        if not even_if_withdrawn and self.withdrawn_by(self.as_of_date):
            return None
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
    def target_date(self):
        """HACK to address due vs start/available confusion

        TN-2468 captures how the original intent of due was lost and
        became the start/available date.  Until this is cleaned up (
        by replacing OverallStatus.due with OverallStatus.start and
        all related usage) continue to treat due == start/available
        and provide a `target_date` for the QB.calculated_due value.
        """
        return self._target_date

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

        results = self.__instruments_by_strategy(classification, needing_full)
        self.warn_on_duplicate_request(set(results))
        return results

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
        self.warn_on_duplicate_request(set(in_progress))

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

    def withdrawn_by(self, timepoint):
        """Returns true if user had withdrawn by given timepoint"""
        return self._withdrawal_date and self._withdrawal_date <= timepoint

    def warn_on_duplicate_request(self, requested_set):
        """Ugly hack to catch TN-2747 in the act

        If the requested set includes the `irondemog_v3` - confirm we don't
        already have one on file for the user.  Log an error if found, to
        alert staff.

        Once bug is found and resolved, remove!
        """
        from .questionnaire_response import QuestionnaireResponse

        requested = requested_set.intersection(('irondemog', 'irondemog_v3'))
        if not requested:
            return

        # Can't imagine we'll ever request both versions!
        if len(requested) != 1:
            raise ValueError(f"both indefinites requested! {requested}")

        # as the requested list includes one of the indefinites,
        # make sure we don't already have a completed one
        requested_indef = requested.pop()
        query = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == self.user.id).filter(
            QuestionnaireResponse.status == 'completed').filter(
            QuestionnaireResponse.document[
                ('questionnaire', 'reference')].astext.endswith(
                requested_indef)).count()
        if query != 0:
            current_app.logger.error(
                f"Caught TN-2747 in action!  User {self.user.id} completed"
                f" {requested_indef} already!")


def patient_research_study_status(patient, ignore_QB_status=False):
    """Returns details regarding patient readiness for available studies

    Wraps complexity of checking multiple QB_Status and ResearchStudy
    availability.  Includes several business rule checks as well
    as enforcing user has completed outstanding work from other studies
    if applicable.  NB - a user may be "ready" for a study, but another
    study may have outstanding work.

    :param patient: subject to check
    :param ignore_QB_status: set to prevent recursive call, if used during
      process of evaluating QB_status.  Will restrict results to eligible
    :returns: dictionary of applicable studies keyed by research_study_id.
      Each contains a dictionary with keys:
     - eligible: set True if assigned to research study and pre-requisites
         have been met, such as assigned clinician if applicable.
     - ready: set True or False based on complex rules.  True means pending
         work user can immediately do.  NOT determined w/ ``ignore_QB_status``
     - intervention_qnr_eligible: if false, staff controls should be disabled.
         True means no criteria found preventing outstanding staff work.
     - errors: list of strings detailing anything preventing user from being
         "ready"

    """
    from datetime import datetime
    from .research_study import EMPRO_RS_ID, ResearchStudy
    as_of_date = datetime.utcnow()

    results = {}
    # check studies in required order - first found with pending work
    # preempts subsequent
    for rs in ResearchStudy.assigned_to(patient):
        rs_status = {
            'eligible': True,
            'ready': False,
            'intervention_qnr_eligible': True,
            'errors': [],
        }
        results[rs] = rs_status
        if rs == EMPRO_RS_ID and len([c for c in patient.clinicians]) == 0:
            # Enforce biz rule - must have clinician on file.
            trace("no clinician; not eligible")
            rs_status['eligible'] = False
            rs_status['intervention_qnr_eligible'] = False
            rs_status['errors'].append("No clinician")

        if ignore_QB_status:
            # Bootstrap issues, can't yet check QB_Status.
            continue

        assessment_status = QB_Status(
            patient, research_study_id=rs, as_of_date=as_of_date)
        if assessment_status.overall_status == OverallStatus.withdrawn:
            rs_status['errors'].append('Withdrawn')
            continue
        if assessment_status.overall_status == OverallStatus.expired:
            rs_status['errors'].append('Expired')
            continue

        needing_full = assessment_status.instruments_needing_full_assessment(
            classification='all')
        resume_ids = assessment_status.instruments_in_progress(
            classification='all')

        if needing_full or resume_ids:
            # work to be done in this study
            rs_status['ready'] = True

        # Apply business rules specific to EMPRO
        if rs == EMPRO_RS_ID:
            if results[0]['ready']:
                # Clear ready status when base has pending work
                rs_status['ready'] = False
                rs_status['errors'].append('Pending work in base study')
            elif not patient.email_ready():
                # Avoid errors from automated emails, that is, email required
                rs_status['ready'] = False
                rs_status['errors'].append('User lacks valid email address')
            elif rs_status['ready']:
                # As user may have just entered ready status on EMPRO
                # move trigger_states.state to due
                from ..trigger_states.empro_states import initiate_trigger
                initiate_trigger(patient.id)

    return results
