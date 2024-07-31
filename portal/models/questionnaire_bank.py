"""Questionnaire Bank module"""

from flask import url_for
from flask_babel import gettext as _
from flask_sqlalchemy_caching import FromCache
from sqlalchemy import CheckConstraint, Enum, UniqueConstraint

from ..cache import FIVE_MINS, TWO_HOURS, cache
from ..database import db
from ..date_tools import RelativeDelta
from ..trace import trace
from ..trigger_states.models import TriggerState
from .clinical_constants import CC
from .fhir import bundle_results
from .intervention import Intervention, INTERVENTION
from .intervention_strategies import observation_check
from .qbd import QBD
from .questionnaire import Questionnaire
from .recur import Recur
from .reference import Reference
from .research_protocol import ResearchProtocol
from .user_consent import consent_withdrawal_dates

classification_types = ('baseline', 'recurring', 'indefinite', 'other')
classification_types_enum = Enum(
    *classification_types, name='classification_enum', create_type=False)


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
        Recur, lazy='joined', secondary='questionnaire_bank_recurs')

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

    @property
    def research_study_id(self):
        """A questionnaire bank w/ a research protocol has a research study"""
        # intervention linked qbs hardcoded to use study id 0
        if self.intervention_id is not None:
            return 0

        if self.research_protocol_id is None:
            return

        return self.research_protocol.research_study_id

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
        # retain the recurrence associated with the QB_id and iteration
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

    def calculated_start(self, trigger_date):
        """Return QBD (QB Details) for QB

        :param trigger_date: initial trigger utc time value

        Given a self.classification of ``baseline`` or ``indefinite``, return
        a QBD with the ``relative_start`` value defining the calculated start
        in UTC, for this QB.

        NB, a recurring QB requires more information, such as the iteration,
        and will therefore raise a ``ValueError``.

        :return: QBD (datetime of the questionnaire's start date,
            iteration_count, recurrence, and self QB field)

        """
        if self.classification not in ('baseline', 'indefinite'):
            raise ValueError("unsupported classification {}".format(
                self.classification))

        # As this is restricted to baseline and indefinite - iteration and
        # recur are always None
        return QBD(
            relative_start=(trigger_date + RelativeDelta(self.start)),
            iteration=None, recur=None, questionnaire_bank=self)

    def calculated_expiry(self, start):
        """Return calculated expired date (UTC) for QB or None"""
        return start + RelativeDelta(self.expired)

    def calculated_due(self, start):
        """Return calculated due date (UTC) for QB or start"""
        if not self.due:
            return start

        return start + RelativeDelta(self.due)

    def calculated_overdue(self, start):
        """Return calculated overdue given start date, or None if N/A"""
        if not self.overdue:
            return None

        return start + RelativeDelta(self.overdue)

    @staticmethod
    @cache.memoize(timeout=FIVE_MINS)
    def name_map():
        """For reporting purposes, generate a map of QB.id to names"""
        qb_name_map = {qb.id: qb.name for qb in QuestionnaireBank.query.all()}
        # add None to make "safe" for clients w/o checks
        qb_name_map[None] = "None"
        return qb_name_map


@cache.memoize(timeout=FIVE_MINS)
def trigger_date(user, research_study_id, qb=None):
    """Return trigger date for user, research_study

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

    :param user: subject of query
    :param research_study_id: research study being processed
    :param qb: QuestionnaireBank if available (really only necessary
        to distinguish different behavior on recurring RP case).
    :return: UTC datetime for the given user / QB, or None if N/A

    """
    from .qb_timeline import QBT
    from .research_study import EMPRO_RS_ID
    trace("calculate trigger date (not currently cached)")

    def consent_date(user, research_study_id):
        consent, _ = consent_withdrawal_dates(user, research_study_id=research_study_id)
        if consent:
            trace('found valid_consent with trigger_date {}'.format(
                consent))
            return consent

    def completed_global_date(user, consent_date):
        """EMPRO requires a global study completed w/i 4 weeks

        :returns: the completed datetime of a global study QB either
          prior to consent_date, but within 4 weeks or
          after consent_date or
          None

        """
        four_weeks_back = consent_date - RelativeDelta(weeks=4)
        completed = QBT.query.filter(QBT.user_id == user.id).filter(
            QBT.status == 'completed').filter(
            QBT.research_study_id == 0).filter(
            QBT.at > four_weeks_back).order_by(QBT.at).with_entities(
            QBT.at)

        best = None
        for timepoint in completed:
            if not best:
                best = timepoint.at
                continue
            if timepoint.at > consent_date:
                # already have a match, don't accept a "better" option
                # beyond the consent date.
                break
        return best

    trigger = None

    if research_study_id == EMPRO_RS_ID:
        c_date = consent_date(user, research_study_id)
        if not c_date:
            return None
        completed_global = completed_global_date(user, c_date)
        if not completed_global:
            # User didn't complete a global study within four weeks prior to
            # their consent date.  BUT we may be looking this up at a later
            # date.  In a situation in which, on initial consent, the above
            # was true, and the next global visit hadn't started yet, the user
            # could legitimately start their EMPRO.
            #
            # However, looking this up at a later date when the subsequent
            # global visit is due, they would NOT be allowed to begin work
            # on EMPRO, until that global visit was completed.
            #
            # Therefore, if they did start EMPRO before the subsequent became
            # due, we can't move the trigger date, and must stick with the
            # original.  Should there be any rows in trigger_states for the
            # user prior to the subsequent global due date, use consent date.
            next_global_due = QBT.query.filter(QBT.user_id == user.id).filter(
                QBT.status == 'due').filter(
                QBT.research_study_id == 0).filter(
                QBT.at > c_date).order_by(QBT.at).with_entities(
                QBT.at).first()
            if not next_global_due:
                # No subsequent found - N/A
                return None
            trigger_states = TriggerState.query.filter(
                TriggerState.user_id == user.id).filter(
                TriggerState.timestamp < next_global_due)

            if trigger_states.count():
                # Found subsequent global work due and EMPRO work commenced
                # prior to the subsequent global, return consent date.
                return c_date

            return None
        if completed_global < c_date:
            return c_date
        return completed_global

    # If given a QB, use its details to determine trigger
    if qb and qb.research_protocol_id:
        if not trigger:
            trigger = consent_date(user, research_study_id=research_study_id)

        if not trigger:
            trace(
                "questionnaire_bank affiliated with RP {}, user has no"
                " valid consents, so no trigger_date".format(
                    qb.research_protocol_id))
        return trigger

    # Without a qb, use consent date if an RP is found.
    if ResearchProtocol.assigned_to(user, research_study_id):
        return consent_date(user, research_study_id=research_study_id)


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


def qbs_by_intervention(user, classification):
    """returns QBs associated with the user via intervention"""
    results = []

    # Some systems have zero intervention qbs - bail early if that's the case
    # potential query caching requires db.session merge
    iqbs = [db.session.merge(i, load=False)
            for i in intervention_qbs(classification)]
    if not iqbs:
        return results

    # At this time, doesn't apply to metastatic patients.
    if user.concept_value(CC.PCaLocalized) in ('unknown', 'true'):

        # Complicated rules (including strategies and UserIntervention
        # rows) define a user's access to an intervention. Rely on the
        # same check used to display the intervention cards, and only
        # check if intervention is associated with QBs.

        for qb in iqbs:
            intervention = Intervention.query.get(qb.intervention_id)
            if intervention.quick_access_check(user):
                # TODO: business rule details like the following should
                # move to site persistence for QB to user mappings.
                check_func = observation_check("biopsy", 'true')
                if check_func(intervention=intervention, user=user):
                    if qb not in results:
                        results.append(qb)
    return results


@cache.memoize(timeout=TWO_HOURS)
def intervention_qbs(classification):
    """return all QBs associated with interventions

    NB - as the results may be cached and expected to be live db session
    objects, clients should confirm results are in the session or call
    db.session.merge(load=False)

    :param classification: set to restrict to given classification
    :returns: all matching QuestionnaireBanks

    """
    query = QuestionnaireBank.query.filter(
        QuestionnaireBank.intervention_id.isnot(None))
    if classification:
        query = query.filter(
            QuestionnaireBank.classification == classification)

    if not query.count():
        return []
    return query.all()


@cache.memoize(timeout=TWO_HOURS)
def qbs_by_rp(rp_id, classification):
    """return QBs associated with a given research protocol

    NB - as the results may be cached and expected to be live db session
    objects, clients should confirm results are in the session or call
    db.session.merge(load=False)

    :param rp_id: research protocol id associated with QBs
    :param classification: set to restrict to given classification
    :returns: all matching QuestionnaireBanks

    """
    results = QuestionnaireBank.query.filter(
        QuestionnaireBank.research_protocol_id == rp_id).options(
        FromCache(cache))
    if classification:
        results = results.filter(
            QuestionnaireBank.classification == classification)
        trace("found {} for rp_id {} ({})".format(
            results.count(), rp_id, classification))
    else:
        trace("found {} for rp_id {}".format(results.count(), rp_id))
    return results.all()


def visit_name(qbd):
    from .research_study import (
        EMPRO_RS_ID,
        research_study_id_from_questionnaire,
    )

    if not qbd.questionnaire_bank or qbd.questionnaire_bank.id == 0:
        return None

    rs_id = research_study_id_from_questionnaire(
        qbd.questionnaire_bank.questionnaires[0].name)
    if qbd.recur:
        srd = RelativeDelta(qbd.recur.start)
        if (
                qbd.questionnaire_bank.research_protocol and
                qbd.questionnaire_bank.research_protocol.name.endswith('v5')):
            # TODO: remove this ugly hack.  V5 starts early, must add 1 month
            # but that can't be done across the board as others don't need
            srd += RelativeDelta(months=1)
        sm = srd.months or 0
        sm += (srd.years * 12) if srd.years else 0
        clrd = RelativeDelta(qbd.recur.cycle_length)
        clm = clrd.months or 0
        clm += (clrd.years * 12) if clrd.years else 0
        total = clm * qbd.iteration + sm
        if rs_id == EMPRO_RS_ID:
            return _('Month %(month_total)d', month_total=total+1)
        return _('Month %(month_total)d', month_total=total)

    if rs_id == EMPRO_RS_ID:
        return _('Month %(month_total)d', month_total=1)
    return _(qbd.questionnaire_bank.classification.title())


def add_static_questionnaire_bank():
    """Insert special `none of the above` at index 0"""
    existing = QuestionnaireBank.query.get(0)
    if not existing:
        db.session.add(QuestionnaireBank(
            id=0,
            name='none of the above',
            classification='other',
            start="{'days': 0}",
            intervention_id=INTERVENTION.DEFAULT.id))
