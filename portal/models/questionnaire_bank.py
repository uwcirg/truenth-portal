"""Questionnaire Bank module"""
from collections import namedtuple
from datetime import MAXYEAR, datetime

from flask import current_app, url_for
from flask_babel import gettext as _
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM

from ..database import db
from ..date_tools import RelativeDelta
from ..trace import trace
from .clinical_constants import CC
from .fhir import bundle_results
from .intervention import Intervention
from .intervention_strategies import observation_check
from .procedure_codes import latest_treatment_started_date
from .questionnaire import Questionnaire
from .questionnaire_response import QuestionnaireResponse
from .recur import Recur
from .reference import Reference

classification_types = ('baseline', 'followup', 'recurring', 'indefinite')
classification_types_enum = ENUM(
    *classification_types, name='classification_enum', create_type=False)

QBD = namedtuple('QBD', ['relative_start', 'iteration',
                         'recur', 'questionnaire_bank'])


class QuestionnaireBank(db.Model):
    __tablename__ = 'questionnaire_banks'
    __table_args__ = (
        CheckConstraint('NOT(research_protocol_id IS NULL AND '
                        'intervention_id IS NULL) '
                        'AND NOT(research_protocol_id IS NOT NULL AND '
                        'intervention_id IS NOT NULL)'),)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    classification = db.Column(
        'classification', classification_types_enum,
        server_default='baseline', nullable=False)

    start = db.Column(
        db.Text, nullable=False,
        doc=("'relativedelta' value (i.e. {\"months\": 3, \"days\": -14}) "
             "from trigger date noting the beginning of the valid time "
             "period for the questionnaire bank"))
    due = db.Column(
        db.Text, nullable=True,
        doc=("optional 'relativedelta' value from start, noting when "
             "the questionnaire bank is considered 'due'"))
    overdue = db.Column(
        db.Text, nullable=True,
        doc=("optional 'relativedelta' value from start, noting when "
             "the questionnaire bank is considered 'overdue'"))
    expired = db.Column(
        db.Text, nullable=True,
        doc=("'relativedelta' value from start defining the exclusive end "
             "of the valid time period for the questionnaire bank"))
    questionnaires = db.relationship(
        'QuestionnaireBankQuestionnaire',
        back_populates='questionnaire_bank',
        order_by="QuestionnaireBankQuestionnaire.rank")
    recurs = db.relationship(
        Recur, secondary='questionnaire_bank_recurs')

    # QuestionnaireBank is associated with ResearchProtocol XOR Intervention,
    # either of which dictate whether it's given to a User
    research_protocol_id = db.Column(
        db.ForeignKey('research_protocols.id'), nullable=True)
    intervention_id = db.Column(
        db.ForeignKey('interventions.id'), nullable=True)

    communication_requests = db.relationship(
        'CommunicationRequest')
    research_protocol = db.relationship('ResearchProtocol')

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "QuestionnaireBank {0.id} {0.name} {0.classification}".format(
            self)

    @property
    def display_name(self):
        """Generate and return 'Title Case' version of name 'title_case' """
        if not self.name:
            return
        word_list = self.name.split('_')
        return ' '.join([n.title() for n in word_list])

    @classmethod
    def from_json(cls, data):
        instance = cls()
        return instance.update_from_json(data)

    def update_from_json(self, data):
        self.name = data['name']
        if 'classification' in data:
            self.classification = data['classification']
        if 'research_protocol' in data:
            self.research_protocol_id = Reference.parse(
                data['research_protocol']).id
        if 'intervention' in data:
            self.intervention_id = Reference.parse(
                data['intervention']).id
        self.start = data['start']
        RelativeDelta.validate(self.start)
        self.expired = data['expired']
        RelativeDelta.validate(self.expired)
        if 'due' in data:
            self.due = data['due']
            RelativeDelta.validate(self.due)
        if 'overdue' in data:
            self.overdue = data['overdue']
            RelativeDelta.validate(self.overdue)

        self = self.add_if_not_found(commit_immediately=True)

        rs_named = set()
        for r in data.get('recurs', []):
            recur = Recur.from_json(r).add_if_not_found()
            if recur not in self.recurs:
                self.recurs.append(recur)
            rs_named.add(recur)

        # remove any stale
        for unwanted in set(self.recurs) - rs_named:
            self.recurs.remove(unwanted)
            db.session.delete(unwanted)

        # enforce inability to handle multiple recurs per QB
        # If this is ever needed, several tables will need to
        # retain the recur associated with the QB_id and iteration
        if len(self.recurs) > 1:
            raise ValueError(
                "System cannot handle multiple recurs per QB. "
                "review definition for QB {}".format(self.name))

        def purge_rank_conflicts(questionnaire):
            # if a different q is assigned to the same rank, it'll lead to
            # an integrity error - must remove the stale first
            match = [
                q for q in self.questionnaires if
                q.rank == questionnaire.rank]
            if (match and match[0].questionnaire_id !=
                    questionnaire.questionnaire_id):
                self.questionnaires.remove(match[0])
                db.session.delete(match[0])

        qs_named = set()
        for q in data['questionnaires']:
            questionnaire = QuestionnaireBankQuestionnaire.from_json(
                q)
            purge_rank_conflicts(questionnaire)
            questionnaire.questionnaire_bank_id = self.id
            questionnaire = questionnaire.add_if_not_found(True)
            if questionnaire not in self.questionnaires:
                self.questionnaires.append(questionnaire)
            qs_named.add(questionnaire)

        # remove any stale
        for unwanted in set(self.questionnaires) - qs_named:
            self.questionnaires.remove(unwanted)
            db.session.delete(unwanted)

        return self

    def as_json(self):
        d = {}
        d['resourceType'] = 'QuestionnaireBank'
        d['name'] = self.name
        d['start'] = self.start
        d['expired'] = self.expired
        if self.due:
            d['due'] = self.due
        if self.overdue:
            d['overdue'] = self.overdue
        d['classification'] = self.classification
        if self.research_protocol:
            d['research_protocol'] = Reference.research_protocol(
                self.research_protocol.name).as_fhir()
        if self.intervention_id:
            d['intervention'] = Reference.intervention(
                self.intervention_id).as_fhir()
        d['questionnaires'] = [q.as_json() for q in self.questionnaires]
        d['recurs'] = [r.as_json() for r in self.recurs]
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries on name alone, adds new if not found.

        @return: the new or matched QuestionnaireBank

        """
        assert self.name
        existing = QuestionnaireBank.query.filter_by(
            name=self.name).first()
        if not existing:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        else:
            self.id = existing.id
        self = db.session.merge(self)
        return self

    @classmethod
    def generate_bundle(cls, limit_to_ids=None):
        """Generate a FHIR bundle of existing questionnaire banks ordered by ID

        If limit_to_ids is defined, only return the matching set, otherwise
        all questionnaire banks found.

        """
        query = QuestionnaireBank.query.order_by(QuestionnaireBank.id)
        if limit_to_ids:
            query = query.filter(QuestionnaireBank.id.in_(limit_to_ids))

        objs = [{'resource': q.as_json()} for q in query]
        link = {
            'rel': 'self', 'href': url_for(
                'questionnaire_api.questionnaire_bank_list', _external=True)}
        return bundle_results(elements=objs, links=[link])

    @staticmethod
    def current_rps(user, as_of_date):
        """returns current research protocols for user's orgs

        :param user: subject of the query
        :param as_of_date: define to return best RP for org considering
            retired date (when org moves to new protocol).  Set to None
            to get all known.
        :returns: list of research protocol identifiers

        """
        user_rps = set()
        for org in (o for o in user.organizations if o.id):
            rp = org.research_protocol(as_of_date=as_of_date)
            if rp:
                user_rps.add(rp.id)
        return user_rps

    @staticmethod
    def qbs_by_org(user, classification, as_of_date):
        """return QBs associated with the user via organizations

        :param user: subject of the query
        :param classification: set to restrict to given classification
        :param as_of_date: set to restrict to org's "current" rp WRT given
            date

        """
        results = QuestionnaireBank.query.filter(
            QuestionnaireBank.research_protocol_id.in_(
                QuestionnaireBank.current_rps(user, as_of_date)))
        if classification:
            results = results.filter(
                QuestionnaireBank.classification == classification)
        return results.all()

    @staticmethod
    def qbs_by_intervention(user, classification):
        """returns QBs associated with the user via intervention"""
        results = []

        # At this time, doesn't apply to metastatic patients.
        if user.concept_value(CC.PCaLocalized) in ('unknown', 'true'):

            # Complicated rules (including strategies and UserIntervention
            # rows) define a user's access to an intervention. Rely on the
            # same check used to display the intervention cards, and only
            # check if intervention is associated with QBs.
            intervention_qbs = QuestionnaireBank.query.filter(
                QuestionnaireBank.intervention_id.isnot(None))
            if classification:
                intervention_qbs = intervention_qbs.filter(
                    QuestionnaireBank.classification == classification)

            for qb in intervention_qbs:
                intervention = Intervention.query.get(qb.intervention_id)
                if intervention.quick_access_check(user):
                    # TODO: business rule details like the following should
                    # move to site persistence for QB to user mappings.
                    check_func = observation_check("biopsy", 'true')
                    if check_func(intervention=intervention, user=user):
                        if qb not in results:
                            results.append(qb)
        return results

    @staticmethod
    def qbs_for_user(user, classification, as_of_date):
        """Returns questionnaire banks applicable to (user, classification)

        Looks up the appropriate questionnaire banks for the user.
        Considers both the current mappings (such as affiliation
        through intervention or organization) as well as any in-progress or
        completed questionnaire banks.

        :param user: for whom to look up QBs
        :param classification: set to restrict to a given classification.
        :param as_of_date: as assigned QBs change over time (due to research
         protocol upgrades), required to lookup what applied at the given time.
        :return: list of unique matching QuestionnaireBanks.  Any applicable
         `in_progress` or `completed` will be at head of list.

        """
        if not as_of_date:
            raise ValueError("requires valid as_of_date")

        def validate_classification_count(qbs):
            """Only allow a single QB for baseline and indefinite"""
            if qbs and qbs[0].classification == 'recurring':
                return
            if len(qbs) > 1:
                errstr = ("multiple QuestionnaireBanks for {user} with "
                          "{classification} found.  The UI won't correctly "
                          "display more than one at this "
                          "time.").format(user=user,
                                          classification=classification)
                if current_app.config.get('TESTING'):
                    raise ValueError(errstr)
                current_app.logger.error(errstr)

        def submitted_qbs(user, classification):
            """return list QBs for which the user already submitted work"""
            submitted = QuestionnaireBank.query.join(
                QuestionnaireResponse).filter(
                    QuestionnaireResponse.subject_id == user.id,
                    QuestionnaireResponse.questionnaire_bank_id ==
                    QuestionnaireBank.id).order_by(
                QuestionnaireResponse.authored.desc())
            if classification:
                submitted = submitted.filter(
                    QuestionnaireBank.classification == classification)
            return submitted.all()

        # collate submitted QBs, QBs by org and QBs by intervention
        in_progress = submitted_qbs(user=user, classification=classification)
        by_org = QuestionnaireBank.qbs_by_org(
            user=user, classification=classification, as_of_date=as_of_date)
        by_intervention = QuestionnaireBank.qbs_by_intervention(
            user=user, classification=classification)

        if in_progress and classification in ('baseline', 'indefinite'):
            # Need one QB for baseline, indef - prefer in_progress
            results = in_progress
        else:
            # combine current with in-progress
            # maintain order by relative start for most_current_qb filtering
            # in-progress takes precedence
            in_progress_set = set(in_progress)  # O(n)
            others = set(by_org + by_intervention)
            results = in_progress + [
                e for e in others if e not in in_progress_set]

            # additional sort is necessary in case of both as in_progress
            # wasn't necessarily all inclusive (i.e. user may have skipped
            # one or more).  such gaps break most_current_qb filtering
            if all((in_progress, others)):
                someday = datetime(year=MAXYEAR, month=12, day=31)
                sort_results = {}
                for qb in results:
                    trigger_date = qb.trigger_date(user=user)
                    start = (
                        qb.calculated_start(
                            trigger_date=trigger_date,
                            as_of_date=as_of_date).relative_start or someday)

                    if start not in sort_results:
                        sort_results[start] = qb
                results = [
                    sort_results[k] for k in sorted(sort_results.keys())]

        validate_classification_count(results)
        return results

    @staticmethod
    def most_current_qb(user, as_of_date):
        """Return namedtuple (QBD) for user representing their most current QB

        Return namedtuple of QB Details for user, containing the current QB,
        the QB's calculated start date, the current QB recurrence, and the
        recurrence iteration number. Values are set as None if N/A.

        :param as_of_date: utc time value for computation, i.e. utcnow()

        Ideally, return the one current QuestionnaireBank that applies
        to the user 'as_of_date'.  If none, return the most recently
        expired.

        NB the `indefinite` classification is outside the scope of this method,
        and should be treated independently - see `indefinite_qb`

        """
        assert(as_of_date)
        baseline = QuestionnaireBank.qbs_for_user(
            user, 'baseline', as_of_date=as_of_date)
        if not baseline:
            trace("no baseline questionnaire_bank, can't continue")
            return QBD(None, None, None, None)

        if not baseline[0].trigger_date(user):
            trace("no baseline trigger date, can't continue")
            return QBD(None, None, None, None)

        # Iterate over users QBs looking for current
        last_found = QBD(relative_start=None, iteration=None, recur=None,
                         questionnaire_bank=baseline[0])
        for classification in classification_types:
            if classification == 'indefinite':
                continue
            for qb in QuestionnaireBank.qbs_for_user(
                    user, classification, as_of_date=as_of_date):
                trigger_date = qb.trigger_date(user)
                qbd = qb.calculated_start(trigger_date, as_of_date)
                if qbd.relative_start is None:
                    # indicates QB hasn't started yet, continue
                    continue
                expiry = qb.calculated_expiry(trigger_date, as_of_date)
                last_found = qbd._replace(questionnaire_bank=qb)

                if qbd.relative_start <= as_of_date and as_of_date < expiry:
                    trace("most_recent found {}".format(last_found))
                    return last_found
        trace("most_recent found {}".format(last_found))
        return last_found

    @staticmethod
    def indefinite_qb(user, as_of_date):
        """Return namedtuple (QBD) for user representing their indefinite QB

        The `indefinite` case is special.  Static method for this special case
        as `most_current_qb()` handles all others.  Same return type, a QBD
        named tuple.

        :returns QBD: with values only if the user has an indefinite qb

        """
        indefinite_qb = QuestionnaireBank.qbs_for_user(
            user, classification='indefinite', as_of_date=as_of_date)
        no_qb = QBD(None, None, None, None)

        if not indefinite_qb:
            return no_qb

        if len(indefinite_qb) > 1:
            raise ValueError("only supporting single indefinite QB")

        as_of_date = as_of_date or datetime.utcnow()
        trigger_date = indefinite_qb[0].trigger_date(user)

        # Without basic requirements, such as a consent, the trigger
        # date can't be calculated.  Without a trigger, the user doesn't
        # get an indefinite qb.
        if not trigger_date:
            return no_qb

        return indefinite_qb[0].calculated_start(
            trigger_date=trigger_date, as_of_date=as_of_date)

    def recurring_starts(self, trigger_date):
        """Generator for each successive QBD in a recurrence

        :param trigger_date: initial trigger utc time value
        :returns: QBD for each valid iteration till the QB recurrences
            are terminated

        """
        for recur in self.recurs:
            ic = 0  # reset iteration count on each recur instance
            term_date = trigger_date + RelativeDelta(recur.termination)
            while True:
                start = (trigger_date + RelativeDelta(self.start) +
                         RelativeDelta(recur.start) +
                         (ic * RelativeDelta(recur.cycle_length)))
                if start > term_date:
                    break
                yield QBD(
                    relative_start=start, iteration=ic, recur=recur,
                    questionnaire_bank=self)
                ic += 1

    def calculated_start(self, trigger_date, as_of_date):
        """Return namedtuple (QBD) for QB

        :param trigger_date: initial trigger utc time value
        :param as_of_date: utc time value for computation, i.e. utcnow()

        Returns namdetuple (QBD) containing the calculated start date in UTC
        for the QB, the QB's recurrence, and the iteration count.  Generally
        trigger date plus the QB.start.  For recurring, the iteration count may
        be non zero if it takes multiple iterations to reach the active cycle.

        :return: namedtuple QBD (datetime of the questionnaire's start date,
            iteration_count, recurrence, and self QB field);
            QBD(None, None, None, self) if N/A

        """
        # On recurring QB, delegate to recur for date
        if len(self.recurs):
            for recurrence in self.recurs:
                (relative_start, ic) = recurrence.active_interval_start(
                    trigger_date=trigger_date, as_of_date=as_of_date)
                if relative_start:
                    return QBD(relative_start=relative_start, iteration=ic,
                               recur=recurrence, questionnaire_bank=self)
            # no active recurrence
            return QBD(relative_start=None, iteration=None,
                       recur=None, questionnaire_bank=self)

        # Otherwise, simply trigger plus start (and iteration_count of None)
        return QBD(relative_start=(trigger_date + RelativeDelta(self.start)),
                   iteration=None, recur=None, questionnaire_bank=self)

    def calculated_expiry(self, trigger_date, as_of_date):
        """Return calculated expired date (UTC) for QB or None"""
        start = self.calculated_start(trigger_date, as_of_date).relative_start
        if not start:
            return None
        return start + RelativeDelta(self.expired)

    def calculated_due(self, trigger_date, as_of_date):
        """Return calculated due date (UTC) for QB or None"""
        start = self.calculated_start(trigger_date, as_of_date).relative_start
        if not (start and self.due):
            return None

        return start + RelativeDelta(self.due)

    def calculated_overdue(self, trigger_date, as_of_date):
        """Return calculated overdue date (UTC) for QB or None"""
        start = self.calculated_start(trigger_date, as_of_date).relative_start
        if not (start and self.overdue):
            return None

        return start + RelativeDelta(self.overdue)

    def trigger_date(self, user):
        """Return trigger date for user via QB association

        The trigger date for a questionnaire bank depends on its
        association.  i.e. for org affiliated QBs, use the respective
        consent date.

        NB `trigger_date` is not the same as the start or valid time frame for
        all of a user's Questionnaire Banks.  The trigger date defines the
        initial single period in time for all QBs for a user.  This is an event
        such as the original date of consent with an organization, or the start
        date from a procedure.  QBs valid time frame is in reference to this
        one trigger date.  (Yes, it may be adjusted in time if the user adds a
        new procedure or the consent date is modified).

        :return: UTC datetime for the given user / QB, or None if N/A

        """
        if hasattr(self, '__trigger_date'):
            return self.__trigger_date
        # TODO: business rule details like the following should
        # move to site persistence for QB to user mappings.
        elif self.research_protocol_id:
            # if recurring QB, use the patient's last treatment date, if found
            if self.recurs:
                tx_date = latest_treatment_started_date(user)
                if tx_date:
                    trace(
                        "found latest treatment date {} "
                        "for trigger_date".format(
                            tx_date))
                    self.__trigger_date = tx_date
                    return self.__trigger_date
            # otherwise, use the common top level consent date
            if user.valid_consents and user.valid_consents.count() > 0:
                # consents are ordered desc(acceptance_date), ignore suspended
                # but include deleted, as in a suspended state, the previous
                # acceptance will now be marked deleted.
                for con in user.all_consents:
                    if con.status != 'suspended':
                        self.__trigger_date = con.acceptance_date
                        trace(
                            'found valid_consent with trigger_date {}'.format(
                                self.__trigger_date))
                        return self.__trigger_date
            else:
                trace(
                    "questionnaire_bank affiliated with RP {}, user has "
                    "no valid consents, so no trigger_date".format(
                        self.research_protocol))
                self.__trigger_date = None
                return self.__trigger_date
        elif self.intervention_id:
            # use the patient's last treatment date, if found
            tx_date = latest_treatment_started_date(user)
            if tx_date:
                trace(
                    "found latest treatment date {} for trigger_date".format(
                        tx_date))
                self.__trigger_date = tx_date
                return self.__trigger_date
            # otherwise, use the patient's biopsy date
            self.__trigger_date = user.fetch_datetime_for_concept(
                CC.BIOPSY)
            if self.__trigger_date:
                trace(
                    "found biopsy {} for trigger_date".format(
                        self.__trigger_date))
                return self.__trigger_date
            else:
                trace("no treatment or biopsy date, no trigger_date")
                return self.__trigger_date
        else:
            raise ValueError(
                "Can't compute trigger_date on QuestionnaireBank with "
                "neither research protocol nor intervention associated")

    @staticmethod
    def withdrawal_date(user):
        """Return withdrawal date for user via QB association

        Withdrawal date currently has little to do with the QB, defined here
        for symmetry with trigger_date.

        :return: UTC datetime of withdrawal for given user, or None if N/A

        """
        if user.valid_consents and user.valid_consents.count() > 0:
            # consents are ordered desc(acceptance_date).  only if the
            # first is 'suspended' are we in a withdrawn state
            top_consent = user.valid_consents[0]
            if top_consent.status == 'suspended':
                trace(
                    'found withdrawn {}'.format(top_consent.acceptance_date))
                return top_consent.acceptance_date
        return None


class QuestionnaireBankQuestionnaire(db.Model):
    """link table for n:n association between Questionnaires and Banks"""
    __tablename__ = 'questionnaire_bank_questionnaires'
    id = db.Column(db.Integer(), primary_key=True)
    questionnaire_bank_id = db.Column(db.Integer(), db.ForeignKey(
        'questionnaire_banks.id', ondelete='CASCADE'), nullable=False)
    questionnaire_id = db.Column(db.Integer(), db.ForeignKey(
        'questionnaires.id', ondelete='CASCADE'), nullable=False)
    rank = db.Column(db.Integer, nullable=False)

    questionnaire = db.relationship(Questionnaire)
    questionnaire_bank = db.relationship('QuestionnaireBank')

    __table_args__ = (
        UniqueConstraint(
            questionnaire_bank_id, questionnaire_id,
            name='_questionnaire_bank_questionnaire'),
        UniqueConstraint(
            questionnaire_bank_id, rank,
            name='_questionnaire_bank_questionnaire_rank')
    )

    def __str__(self):
        """Print friendly format for logging, etc."""
        return ("QuestionnaireBankQuestionnaire "
                "{0.questionnaire_bank_id}:{0.questionnaire_id}".format(self))

    @property
    def name(self):
        """Easy access to linked questionnaire `name`"""
        return self.questionnaire.name

    @classmethod
    def from_json(cls, data):
        """Instantiate from persisted form

        NB - the questionnaire_bank_id is NOT expected, as it's defined
        by nesting in site_persistence

        """
        instance = cls()
        instance.questionnaire_id = Reference.parse(data['questionnaire']).id
        instance.rank = data['rank']
        return instance

    def as_json(self):
        d = {}
        d['questionnaire'] = Reference.questionnaire(self.name).as_fhir()
        d['rank'] = getattr(self, 'rank')
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, adds new if not found.

        @return: the new or matched QuestionnaireBankQuestionnaire

        """
        assert(self.questionnaire_id)
        assert(self.questionnaire_bank_id)
        if self in db.session:
            assert self.id
            return self
        existing = QuestionnaireBankQuestionnaire.query.filter_by(
            questionnaire_bank_id=self.questionnaire_bank_id,
            questionnaire_id=self.questionnaire_id).first()
        if not existing:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        else:
            self.id = existing.id
        self = db.session.merge(self)
        return self


def visit_name(qbd):
    if not qbd.questionnaire_bank:
        return None
    if qbd.recur:
        srd = RelativeDelta(qbd.recur.start)
        sm = srd.months or 0
        sm += (srd.years * 12) if srd.years else 0
        clrd = RelativeDelta(qbd.recur.cycle_length)
        clm = clrd.months or 0
        clm += (clrd.years * 12) if clrd.years else 0
        total = clm * qbd.iteration + sm
        return _('Month %(month_total)d', month_total=total)
    return _(qbd.questionnaire_bank.classification.title())
