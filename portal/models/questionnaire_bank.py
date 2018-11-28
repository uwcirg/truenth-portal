"""Questionnaire Bank module"""
from datetime import MAXYEAR, datetime

from flask import current_app, url_for
from flask_babel import gettext as _
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM

from ..database import db
from ..date_tools import RelativeDelta
from ..dogpile_cache import dogpile_cache
from ..trace import trace
from .clinical_constants import CC
from .fhir import bundle_results
from .intervention import Intervention
from .intervention_strategies import observation_check
from .procedure_codes import latest_treatment_started_date
from .questionnaire import Questionnaire
from .qbd import QBD
from .recur import Recur
from .reference import Reference
from .research_protocol import ResearchProtocol
from .user_consent import latest_consent

classification_types = ('baseline', 'recurring', 'indefinite')
classification_types_enum = ENUM(
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
    def indefinite_qb(user, as_of_date):
        """Return QBD for user representing their indefinite QB

        The `indefinite` case is special.  Static method for this special case
        as `most_current_qb()` handles all others.  Same return type, a QBD.

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

    def calculated_start(self, trigger_date):
        """Return QBD (QB Details) for QB

        :param trigger_date: initial trigger utc time value
        :param as_of_date: utc time value for computation, i.e. utcnow()

        Todo update comment...
        Returns QBD containing the calculated start date in UTC
        for the QB, the QB's recurrence, and the iteration count.  Generally
        trigger date plus the QB.start.  For recurring, the iteration count may
        be non zero if it takes multiple iterations to reach the active cycle.

        :return: QBD (datetime of the questionnaire's start date,
            iteration_count, recurrence, and self QB field);
            QBD(None, None, None, self) if N/A

        """
        # On recurring QB, delegate to recur for date
        if len(self.recurs):
            raise ValueError("don't trust this")
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

    def calculated_expiry(self, trigger_date):
        """Return calculated expired date (UTC) for QB or None"""
        start = self.calculated_start(trigger_date).relative_start
        if not start:
            return None
        return start + RelativeDelta(self.expired)

    def calculated_due(self, trigger_date):
        """Return calculated due date (UTC) for QB or None"""
        start = self.calculated_start(trigger_date).relative_start
        if not (start and self.due):
            return None

        return start + RelativeDelta(self.due)

    def calculated_overdue(self, trigger_date):
        """Return calculated overdue date (UTC) for QB or None"""
        start = self.calculated_start(trigger_date).relative_start
        if not (start and self.overdue):
            return None

        return start + RelativeDelta(self.overdue)


def trigger_date(user, qb=None):
    """Return trigger date for user

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
    :param qb: QuestionnaireBank if available (really only necessary
        to distinguish different behavior on recurring RP case).
    :return: UTC datetime for the given user / QB, or None if N/A

    """

    def biopsy_date(user):
        b_date = user.fetch_datetime_for_concept(CC.BIOPSY)
        if b_date:
            trace("found biopsy {} for trigger_date".format(b_date))
            return b_date

    def consent_date(user):
        consent = latest_consent(user)
        if consent:
            trace('found valid_consent with trigger_date {}'.format(
                consent.acceptance_date))
            return consent.acceptance_date

    def tx_date(user):
        t_date = latest_treatment_started_date(user)
        if t_date:
            trace(
                "found latest treatment date {} for trigger_date".format(
                    t_date))
        return t_date

    def intervention_trigger(user):
        # use the patient's last treatment date, if found
        t = tx_date(user)
        # otherwise, use the patient's biopsy date
        if not t:
            t = biopsy_date(user)
        if not t:
            trace("no treatment or biopsy date, no trigger_date")
        return t

    trigger = None

    # If given a QB, use its details to determine trigger
    if qb and qb.research_protocol_id:
        if qb.recurs:
            # if recurring QB, use the patient's last treatment date, if found
            trigger = tx_date(user)

        if not trigger:
            trigger = consent_date(user)

        if not trigger:
            trace(
                "questionnaire_bank affiliated with RP {}, user has no"
                " valid consents, so no trigger_date".format(
                    qb.research_protocol_id))
        return trigger

    elif qb and qb.intervention_id:
        return intervention_trigger(user)

    # Without a qb, use consent date if an RP is found, otherwise try
    # the intervention method.  (Yes, it's possible the user has neither
    # intervention nor RP, but the intervention method is too expensive
    # for a simple trigger date lookup - will be caught in qb_timeline)
    if ResearchProtocol.assigned_to(user):
        return consent_date(user)
    else:
        return intervention_trigger(user)


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
    # Dogpile caching requires sync with session
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


#@dogpile_cache.region('qb_query_cache')
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


#@dogpile_cache.region('qb_query_cache')
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
        QuestionnaireBank.research_protocol_id == rp_id)
    if classification:
        results = results.filter(
            QuestionnaireBank.classification == classification)
        trace("found {} for rp_id {} ({})".format(
            results.count(), rp_id, classification))
    else:
        trace("found {} for rp_id {}".format(results.count(), rp_id))
    return results.all()


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
