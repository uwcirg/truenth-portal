"""Questionnaire Bank module"""
from collections import namedtuple
from datetime import datetime
from flask import current_app, url_for
from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import ENUM

from ..database import db
from ..date_tools import FHIR_datetime, RelativeDelta
from .fhir import CC
from .intervention import Intervention
from .intervention_strategies import observation_check
from .procedure_codes import latest_treatment_started_date
from .questionnaire import Questionnaire
from .recur import Recur
from .reference import Reference
from .research_protocol import ResearchProtocol
from ..trace import trace


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

        qs_named = set()
        for q in data['questionnaires']:
            questionnaire = QuestionnaireBankQuestionnaire.from_json(
                q)
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
        if self.research_protocol_id:
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

        objs = [q.as_json() for q in query]

        bundle = {
            'resourceType': 'Bundle',
            'updated': FHIR_datetime.now(),
            'total': len(objs),
            'type': 'searchset',
            'link': {
                'rel': 'self',
                'href': url_for(
                    'assessment_engine_api.questionnaire_bank_list',
                    _external=True),
            },
            'entry': objs,
        }
        return bundle

    @staticmethod
    def qbs_for_user(user, classification):
        """Return questionnaire banks applicable to (user, classification)

        QuestionnaireBanks are associated with a user through the user's
        organization's (inherited) research_protocols, or through interventions

        :return: matching QuestionnaireBanks if found, else empty list

        """
        user_rps = set()
        for org in (o for o in user.organizations if o.id):
            rp = o.research_protocol
            if rp:
                user_rps.add(rp.id)

        if not user_rps:
            results = []
        elif classification:
            results = QuestionnaireBank.query.filter(
                QuestionnaireBank.research_protocol_id.in_(user_rps),
                QuestionnaireBank.classification == classification).all()
        else:
            results = QuestionnaireBank.query.filter(
                QuestionnaireBank.research_protocol_id.in_(user_rps)).all()

        # Complicated rules (including strategies and UserIntervention rows)
        # define a user's access to an intervention.  Rely on the
        # same check used to display the intervention cards, and only
        # check for interventions actually associated with QBs.
        if classification:
            intervention_associated_qbs = QuestionnaireBank.query.filter(
                QuestionnaireBank.intervention_id.isnot(None),
                QuestionnaireBank.classification == classification)
        else:
            intervention_associated_qbs = QuestionnaireBank.query.filter(
                QuestionnaireBank.intervention_id.isnot(None))
        for qb in intervention_associated_qbs:
            # At this time, doesn't apply to metastatic patients.
            if any((obs.codeable_concept == CC.PCaLocalized
                    and obs.value_quantity == CC.FALSE_VALUE)
                   for obs in user.observations):
                break

            intervention = Intervention.query.get(qb.intervention_id)
            if intervention.quick_access_check(user):
                # TODO: business rule details like the following should
                # move to site persistence for QB to user mappings.
                check_func = observation_check("biopsy", 'true')
                if check_func(intervention=intervention, user=user):

                    results.append(qb)

        def validate_classification_count(qbs):
            if qbs and qbs[0].classification == 'recurring':
                return
            if (len(qbs) > 1):
                errstr = ("multiple QuestionnaireBanks for {user} with "
                          "{classification} found.  The UI won't correctly "
                          "display more than one at this "
                          "time.").format(user=user,
                                          classification=classification)
                systype = current_app.config.get('SYSTEM_TYPE', '').lower()
                if systype == 'production':
                    current_app.logger.error(errstr)
                else:
                    current_app.logger.warn(errstr)

        validate_classification_count(results)
        return results

    @staticmethod
    def most_current_qb(user, as_of_date=None):
        """Return namedtuple (QBD) for user representing their most current QB

        Return namedtuple of QB Details for user, containing the current QB,
        the QB's calculated start date, the current QB recurrence, and the
        recurrence iteration number. Values are set as None if N/A.

        :param as_of_date: if not provided, use current utc time.

        Ideally, return the one current QuestionnaireBank that applies
        to the user 'as_of_date'.  If none, return the most recently
        expired.

        NB the `indefinite` classification is outside the scope of this method,
        and should be treated independently

        """
        as_of_date = as_of_date or datetime.utcnow()

        baseline = QuestionnaireBank.qbs_for_user(user, 'baseline')
        if not baseline:
            trace("no baseline questionnaire_bank, can't continue")
            return QBD(None, None, None, None)
        trigger_date = baseline[0].trigger_date(user)
        if not trigger_date:
            return QBD(None, None, None, None)

        # Iterate over users QBs looking for current
        last_found = QBD(relative_start=None, iteration=None, recur=None,
                         questionnaire_bank=baseline[0])
        for classification in classification_types:
            if classification == 'indefinite':
                continue
            for qb in QuestionnaireBank.qbs_for_user(user, classification):
                qbd = qb.calculated_start(trigger_date, as_of_date)
                if qbd.relative_start is None:
                    # indicates QB hasn't started yet, continue
                    continue
                expiry = qb.calculated_expiry(trigger_date)
                last_found = qbd._replace(questionnaire_bank=qb)

                if qbd.relative_start <= as_of_date and as_of_date < expiry:
                    return last_found
        return last_found

    def calculated_start(self, trigger_date, as_of_date=None):
        """Return namedtuple (QBD) for QB

        Returns namdetuple (QBD) containing the calculated start date in UTC
        for the QB, the QB's recurrence, and the iteration count.  Generally
        trigger date plus the QB.start.  For recurring, the iteration count may
        be non zero if it takes multiple iterations to reach the active cycle.

        :return: namedtuple QBD (datetime of the questionnaire's start date,
            iteration_count, recurrence, and self QB field);
            QBD(None, None, None, self) if N/A

        """
        # On recurring QB, deligate to recur for date
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
        # use the patient's last treatment date, if possible
        # TODO: business rule details like the following should
        # move to site persistence for QB to user mappings.
        tx_date = latest_treatment_started_date(user)
        if tx_date:
            trace(
                "found latest treatment date {} for trigger_date".format(
                    tx_date))
            self.__trigger_date = tx_date
            return self.__trigger_date
        elif self.research_protocol_id:
            # When linked via research protocol, use the common
            # top level consent date as `trigger` date.
            if user.valid_consents and user.valid_consents.count() > 0:
                self.__trigger_date = user.valid_consents[0].audit.timestamp
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
        else:
            if not self.intervention_id:
                raise ValueError(
                    "Can't compute trigger_date on QuestionnaireBank with "
                    "neither research protocol nor intervention associated")
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
        return "Month {}".format(total)
    return qbd.questionnaire_bank.classification.title()
