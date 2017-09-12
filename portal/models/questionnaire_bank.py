"""Questionnaire Bank module"""
from flask import current_app, url_for
from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import ENUM

from ..database import db
from ..date_tools import FHIR_datetime
from .fhir import CC
from .intervention import Intervention
from .intervention_strategies import observation_check
from .organization import OrgTree
from .procedure_codes import latest_treatment_started_date
from .questionnaire import Questionnaire
from .recur import Recur
from .reference import Reference


classification_types = ('baseline', 'followup', 'recurring', 'indefinite')
classification_types_enum = ENUM(
    *classification_types, name='classification_enum', create_type=False)


class QuestionnaireBank(db.Model):
    __tablename__ = 'questionnaire_banks'
    __table_args__ = (
        CheckConstraint('NOT(organization_id IS NULL AND '
                        'intervention_id IS NULL) '
                        'AND NOT(organization_id IS NOT NULL AND '
                        'intervention_id IS NOT NULL)'),
        )
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    classification = db.Column(
        'classification', classification_types_enum,
        server_default='baseline', nullable=False)
    questionnaires = db.relationship(
        'QuestionnaireBankQuestionnaire',
        back_populates='questionnaire_bank',
        order_by="QuestionnaireBankQuestionnaire.rank")

    # QuestionnaireBank is associated with an Organization OR an Intervention,
    # either of which dictate whether it's given to a User
    organization_id = db.Column(
        db.ForeignKey('organizations.id'), nullable=True)
    intervention_id = db.Column(
        db.ForeignKey('interventions.id'), nullable=True)

    communication_requests = db.relationship(
        'CommunicationRequest')

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
        if 'organization' in data:
            self.organization_id = Reference.parse(
                data['organization']).id
        if 'intervention' in data:
            self.intervention_id = Reference.parse(
                data['intervention']).id
        self = self.add_if_not_found(commit_immediately=True)
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
        d['classification'] = self.classification
        if self.organization_id:
            d['organization'] = Reference.organization(
                self.organization_id).as_fhir()
        if self.intervention_id:
            d['intervention'] = Reference.intervention(
                self.intervention_id).as_fhir()
        d['questionnaires'] = [q.as_json() for q in self.questionnaires]
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, adds new if not found.

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

        QuestionnaireBanks are associated with a user through the top
        level organization affiliation, or through interventions

        :return: matching QuestionnaireBanks if found, else empty list

        """
        users_top_orgs = set()
        for org in (o for o in user.organizations if o.id):
            users_top_orgs.add(OrgTree().find(org.id).top_level())

        if not users_top_orgs:
            results = []
        elif classification:
            results = QuestionnaireBank.query.filter(
                QuestionnaireBank.organization_id.in_(users_top_orgs),
                QuestionnaireBank.classification == classification).all()
        else:
            results = QuestionnaireBank.query.filter(
                QuestionnaireBank.organization_id.in_(users_top_orgs)).all()

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
            display_details = intervention.display_for_user(user)
            if display_details.access:
                # TODO: business rule details like the following should
                # move to site persistence for QB to user mappings.
                check_func = observation_check("biopsy", 'true')
                if check_func(intervention=intervention, user=user):

                    results.append(qb)

        def validate_classification_count(qbs):
            if len(qbs) > 1:
                current_app.logger.error(
                    "multiple QuestionnaireBanks for {user} with "
                    "{classification} found.  The UI won't correctly display "
                    "more than one at this time.".format(
                        user=user, classification=classification))

        validate_classification_count(results)
        return results

    def trigger_date(self, user):
        """Return trigger date for user on questionnaire bank

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
        if self.organization_id:
            # When linked via organization, use the common
            # top level consent date as `trigger` date.
            if user.valid_consents and user.valid_consents.count() > 0:
                    return user.valid_consents[0].audit.timestamp
            else:
                return None
        else:
            if not self.intervention_id:
                self.ValueError(
                    "Can't compute trigger_date on QuestionnaireBank "
                    "with neither organization nor intervention associated")
            # TODO: business rule details like the following should
            # move to site persistence for QB to user mappings.
            tx_date = latest_treatment_started_date(user)
            return (tx_date if tx_date else
                    user.fetch_datetime_for_concept(CC.BIOPSY))


class QuestionnaireBankQuestionnaire(db.Model):
    """link table for n:n association between Questionnaires and Banks"""
    __tablename__ = 'questionnaire_bank_questionnaires'
    id = db.Column(db.Integer(), primary_key=True)
    questionnaire_bank_id = db.Column(db.Integer(), db.ForeignKey(
        'questionnaire_banks.id', ondelete='CASCADE'), nullable=False)
    questionnaire_id = db.Column(db.Integer(), db.ForeignKey(
        'questionnaires.id', ondelete='CASCADE'), nullable=False)
    days_till_due = db.Column(db.Integer, nullable=False)
    days_till_overdue = db.Column(db.Integer, nullable=False)
    rank = db.Column(db.Integer, nullable=False)

    questionnaire = db.relationship(Questionnaire)
    questionnaire_bank = db.relationship('QuestionnaireBank')
    recurs = db.relationship(
        Recur, secondary='questionnaire_bank_questionnaire_recurs')

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
        instance.days_till_due = data['days_till_due']
        instance.days_till_overdue = data['days_till_overdue']
        instance.rank = data['rank']
        for r in data.get('recurs', []):
            instance.recurs.append(Recur.from_json(r).add_if_not_found())
        return instance

    def as_json(self):
        d = {}
        d['questionnaire'] = Reference.questionnaire(self.name).as_fhir()
        for k in ('rank', 'days_till_due', 'days_till_overdue'):
            d[k] = getattr(self, k)
        d['recurs'] = [r.as_json() for r in self.recurs]
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
