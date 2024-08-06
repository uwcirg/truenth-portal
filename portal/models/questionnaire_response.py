from collections import defaultdict, namedtuple
import copy
from datetime import datetime
from dateutil.relativedelta import relativedelta
from html.parser import HTMLParser
import json

from flask import current_app, has_request_context, url_for
from flask_swagger import swagger
import jsonschema
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm.exc import MultipleResultsFound

from ..database import db
from ..date_tools import FHIR_datetime
from ..system_uri import (
    TRUENTH_EXTERNAL_STUDY_SYSTEM,
    TRUENTH_STATUS_EXTENSION,
    TRUENTH_VISIT_NAME_EXTENSION,
)
from .audit import Audit
from .encounter import Encounter
from .fhir import bundle_results
from .overall_status import OverallStatus
from .qbd import QBD
from .questionnaire import Questionnaire
from .questionnaire_bank import (
    QuestionnaireBank,
    QuestionnaireBankQuestionnaire,
    trigger_date,
    visit_name,
)
from .research_study import EMPRO_RS_ID, research_study_id_from_questionnaire
from .reference import Reference
from .user import User, current_user, patients_query
from .user_consent import consent_withdrawal_dates


class NoFutureDates(ValueError):
    """Raised on data validation failures where future dates are verboten"""
    pass


class QuestionnaireResponse(db.Model):

    def default_status(context):
        return context.current_parameters['document']['status']

    __tablename__ = 'questionnaire_responses'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.ForeignKey('users.id'), index=True, nullable=False)
    subject = db.relationship("User", back_populates="questionnaire_responses")
    document = db.Column(JSONB)
    encounter_id = db.Column(
        db.ForeignKey('encounters.id', name='qr_encounter_id_fk'),
        index=True,
        nullable=False)
    questionnaire_bank_id = db.Column(
        db.ForeignKey('questionnaire_banks.id'), nullable=True)
    qb_iteration = db.Column(db.Integer(), nullable=True)

    encounter = db.relationship("Encounter")
    questionnaire_bank = db.relationship("QuestionnaireBank")

    # Fields derived from document content
    status = db.Column(
        ENUM(
            'in-progress',
            'completed',
            name='questionnaire_response_statuses'
        ),
        default=default_status
    )

    @property
    def qb_id(self):
        raise ValueError(
            'questionnaire_bank_id referenced by wrong name `qb_id`')

    @qb_id.setter
    def qb_id(self, value):
        raise ValueError(
            'questionnaire_bank_id assignment to wrong name `qb_id`')

    def __str__(self):
        """Print friendly format for logging, etc."""
        authored = self.document and self.document.get('authored') or ''
        return "QuestionnaireResponse {0.id} for user {0.subject_id} " \
               "{0.status} {1}".format(self, authored)

    def assign_qb_relationship(self, acting_user_id, qbd_accessor=None):
        """Lookup and assign questionnaire bank and iteration

        On submission, and subsequently when a user's state changes (such as
        the criteria for trigger_date), determine the associated questionnaire
        bank and iteration and assign, or clear if no match is found.

        :param acting_user_id: current driver of process, for audit purposes
        :param qbd_accessor: function to look up appropriate QBD for given QNR
          Takes ``as_of_date`` and ``classification`` parameters

        """
        authored = FHIR_datetime.parse(self.document['authored'])
        qn_ref = self.document.get("questionnaire").get("reference")
        qn_name = qn_ref.split("/")[-1] if qn_ref else None
        qn = Questionnaire.find_by_name(name=qn_name)
        research_study_id = None

        if qn_name == 'ironman_ss_post_tx':
            # special case for the EMPRO Staff QB
            from ..trigger_states.empro_states import empro_staff_qbd_accessor
            qbd_accessor = empro_staff_qbd_accessor(self)
            research_study_id = EMPRO_RS_ID
        elif qbd_accessor is None:
            from .qb_status import QB_Status  # avoid cycle
            if self.questionnaire_bank is not None:
                research_study_id = self.questionnaire_bank.research_study_id
            else:
                research_study_id = research_study_id_from_questionnaire(
                    qn_name)

            qbstatus = QB_Status(
                self.subject,
                research_study_id=research_study_id,
                as_of_date=authored)

            def qbstats_current_qbd(as_of_date, classification, instrument):
                # TODO: consider instrument?  Introduced in patching
                #  overlapping QBs from v3->v5
                if as_of_date != authored:
                    raise RuntimeError(
                        "local QB_Status instantiated w/ wrong as_of_date")
                return qbstatus.current_qbd(classification)
            qbd_accessor = qbstats_current_qbd

        initial_qb_id = self.questionnaire_bank_id
        initial_qb_iteration = self.qb_iteration

        # clear both until current values are determined
        self.questionnaire_bank_id, self.qb_iteration = None, None

        classification = (
                qn_name.startswith('irondemog') and 'indefinite' or None)
        qbd = qbd_accessor(
            as_of_date=authored,
            classification=classification,
            instrument=qn_name)

        if qbd and qbd.questionnaire_bank and qn and qn.id in (
                q.questionnaire.id for q in
                qbd.questionnaire_bank.questionnaires):
            self.questionnaire_bank_id = qbd.qb_id
            self.qb_iteration = qbd.iteration
        # if a valid qb wasn't found, try the indefinite option
        else:
            qbd = qbd_accessor(
                as_of_date=authored,
                classification='indefinite',
                instrument=qn_name)
            if qbd and qbd.questionnaire_bank and qn and qn.id in (
                    q.questionnaire.id for q in
                    qbd.questionnaire_bank.questionnaires):
                self.questionnaire_bank_id = qbd.qb_id
                self.qb_iteration = qbd.iteration

        if not self.questionnaire_bank_id:
            current_app.logger.warning(
                "Can't locate QB for patient {}'s questionnaire_response {} "
                "with reference to given instrument {}".format(
                    self.subject_id, self.id, qn_name))
            self.questionnaire_bank_id = 0  # none of the above
            self.qb_iteration = None

        if self.questionnaire_bank_id != initial_qb_id or (
                self.qb_iteration != initial_qb_iteration):
            msg = (
                "Updating to qb_id ({}) and qb_iteration ({}) on"
                " questionnaire_response {}".format(
                    self.questionnaire_bank_id, self.qb_iteration,
                    self.id))
            audit = Audit(
                subject_id=self.subject_id, user_id=acting_user_id,
                context='assessment', comment=msg)
            db.session.add(audit)
            # TN-3140 multiple QNRs found for visit/questionnaire dyad
            # Generate an error for alerts, should this look to be a fresh
            # duplicate.  Ignore if we don't have a valid questionnaire bank
            if self.questionnaire_bank_id > 0:
                query = db.session.query(QuestionnaireResponse).filter(
                    QuestionnaireResponse.subject_id == self.subject_id).filter(
                    QuestionnaireResponse.questionnaire_bank_id ==
                    self.questionnaire_bank_id).filter(
                    QuestionnaireResponse.document[
                        ("questionnaire", "reference")
                    ].astext == self.document['questionnaire']['reference']
                )
                if self.qb_iteration is None:
                    query = query.filter(QuestionnaireResponse.qb_iteration.is_(None))
                else:
                    query = query.filter(QuestionnaireResponse.qb_iteration == self.qb_iteration)

                if query.count() != 1:
                    current_app.logger.error(
                        "Second submission for an existing QNR dyad received."
                        f" Patient: {self.subject_id}, QNR {self.id}"
                    )
        # avoid lengthy lookup in caller
        return research_study_id

    @staticmethod
    def purge_qb_relationship(
            subject_id, research_study_id, acting_user_id):
        """Remove qb association from subject user's QuestionnaireResponses

        An event such as changing consent date potentially alters the
        "visit_name" (i.e. 3 month, baseline, etc.) any existing QNRs
        may have been assigned.  This method removes all such QNR->QB
        associations that may now apply to the wrong QB, forcing subsequent
        recalculation

        """
        audits = []
        matching = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == subject_id).filter(
            QuestionnaireResponse.questionnaire_bank_id.isnot(None))

        for qnr in matching:
            if (
                    qnr.questionnaire_bank and
                    qnr.questionnaire_bank.research_study_id !=
                    research_study_id):
                continue

            audit = Audit(
                user_id=acting_user_id, subject_id=subject_id,
                context='assessment',
                comment="Removing qb_id:iteration {}:{} from QNR {}".format(
                    qnr.questionnaire_bank_id, qnr.qb_iteration, qnr.id))
            audits.append(audit)
            qnr.questionnaire_bank_id = None
            qnr.qb_iteration = None

        for audit in audits:
            db.session.add(audit)

        db.session.commit()

    def purge_related_observations(self):
        """Look up and purge all QNR related observations"""
        from portal.models.observation import Observation
        Observation.query.filter(
            Observation.derived_from == str(self.id)).delete()
        db.session.commit()

    @staticmethod
    def by_identifier(identifier):
        """Query for QuestionnaireResponse(s) with given identifier"""
        if not any((identifier.system, identifier.value)):
            raise ValueError("Can't look up null identifier")

        if identifier.system is None:  # FHIR allows null system
            found = QuestionnaireResponse.query.filter(
                QuestionnaireResponse.document['identifier']['system'].is_(
                    None)).filter(
                QuestionnaireResponse.document['identifier']['value']
                == json.dumps(identifier.value))
        else:
            found = QuestionnaireResponse.query.filter(
                QuestionnaireResponse.document['identifier']['system']
                == json.dumps(identifier.system)).filter(
                QuestionnaireResponse.document['identifier']['value']
                == json.dumps(identifier.value))
        return found.order_by(QuestionnaireResponse.id.desc())

    @staticmethod
    def qnr_state(user_id):
        """Useful in tracking changes, capture a dict of user's QNR state"""
        name_map = QuestionnaireBank.name_map()
        qnrs = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == user_id).with_entities(
            QuestionnaireResponse.id,
            QuestionnaireResponse.questionnaire_bank_id,
            QuestionnaireResponse.qb_iteration,
            QuestionnaireResponse.document)

        return {
            f"qnr {qnr.id}":
                [name_map[qnr.questionnaire_bank_id],
                 qnr.qb_iteration,
                 qnr.document["questionnaire"]["reference"].split("/")[-1]]
            for qnr in qnrs}

    @property
    def document_identifier(self):
        """Return FHIR identifier(s) found within the document"""
        return self.document['identifier']

    @staticmethod
    def validate_authored(authored):
        """Validate the authored value is current or in the past

        Don't allow future authored dates (but allow for up to 60 second
        drift from external services)

        """
        if authored > datetime.utcnow() + relativedelta(seconds=60):
            raise NoFutureDates("future authored dates forbidden")

    @staticmethod
    def validate_document(document):
        """Validate given JSON document against our swagger schema"""
        swag = swagger(current_app)

        draft4_schema = {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'type': 'object',
            'definitions': swag['definitions'],
        }

        validation_schema = 'QuestionnaireResponse'
        # Copy desired schema (to validate against) to outermost dict
        draft4_schema.update(swag['definitions'][validation_schema])
        jsonschema.validate(document, draft4_schema)

    @property
    def document_answered(self):
        """ Return a modified copy of self.document including answer text

        QuestionnaireResponse populated with text answers based on codes
        in valueCoding.  This always returns a *copy* of the document so
        any local or subsequent mutations aren't persisted or found in db
        session cached objects.

        """
        instrument_id = self.document['questionnaire']['reference'].split(
            '/')[-1]
        questionnaire = Questionnaire.find_by_name(name=instrument_id)
        document = copy.deepcopy(self.document)

        def quote_double_quote(value):
            """returns quoted version of double quotes within a value string

            Double quotes embedded in strings break parsers such as CSV.  Only
            reliable quoting is a second double quote.
            """
            if value and '"' in value and '""' not in value:
                return value.replace('"', '""')
            return value

        # return copy of original document if no reference Questionnaire
        # available
        if not questionnaire:
            return document

        questionnaire_map = questionnaire.questionnaire_code_map()

        for question in document.get('group', {}).get('question', ()):

            combined_answers = consolidate_answer_pairs(question['answer'])

            # Separate out text and coded answer, then override text
            text_and_coded_answers = []
            for answer in combined_answers:

                # Add text answer before coded answer
                if list(answer.keys())[0] == 'valueCoding':

                    # Prefer text looked up from code over sibling valueString answer
                    text_answer = questionnaire_map.get(
                        answer['valueCoding']['code'],
                        answer['valueCoding'].get('text')
                    )

                    text_and_coded_answers.append({'valueString': text_answer})
                elif 'valueString' in answer and '"' in answer['valueString']:
                    answer['valueString'] = quote_double_quote(answer['valueString'])

                text_and_coded_answers.append(answer)
            question['answer'] = text_and_coded_answers

        return document

    def extensions(self):
        """Return list of FHIR extensions

        No place within the FHIR spec to associate 'visit name' nor a
        'status' as per business rules (i.e. 'in-progress' becomes
        'partially completed' once the associated QB expires).  Use FHIR
        `extension`s to pass these fields to clients like the front end

        @returns list of FHIR extensions for this instance, typically one for `visit_name`
        """
        from .qb_timeline import expires  # avoid cycle
        results = []
        if self.questionnaire_bank_id is not None:
            qb = QuestionnaireBank.query.get(self.questionnaire_bank_id)
            recur_id = None
            for r in qb.recurs:
                recur_id = r.id
            qbd = QBD(
                relative_start=None, iteration=self.qb_iteration,
                recur_id=recur_id, qb_id=self.questionnaire_bank_id)
            results.append({
                'visit_name': visit_name(qbd),
                'url': TRUENTH_VISIT_NAME_EXTENSION})

            expires_at = expires(self.subject_id, qbd)
            if (expires_at and expires_at < datetime.utcnow() and
                    self.status == 'in-progress'):
                results.append({
                    'status': OverallStatus.partially_completed.name,
                    'url': TRUENTH_STATUS_EXTENSION
                })

        return results

    def link_id(self, link_id):
        """Return linkId JSON as defined in QuestionnaireResponse

        :param link_id: i.e. irondemog_v3.10
        :return: JSON for requested linkId
        """
        for question in self.document["group"]["question"]:
            if question["linkId"] == link_id:
                return question

    def replace_link_id(self, link_id, replacement):
        """Return modified questions for linkId with given JSON

        NB the changes returned here must be assigned to a *copy* of
        self.document["group"]["question"] in order to persist.  This
        method does NOT modify the QNR.

        :param link_id: i.e. irondemog_v3.10
        :return: modified self.document["group"]["question"], with requested
         replacement in place of existing for given linkId
        """
        questions = []
        for question in self.document["group"]["question"]:
            if question["linkId"] == link_id:
                questions.append(replacement)
                continue
            questions.append(question)
        assert len(questions) == len(self.document["group"]["question"])
        return questions

    def as_sdc_fhir(self):
        """
        Return QuestionnaireResponse FHIR in structure expected by SDC $extract service
        """
        qnr = self.document_answered

        qn_ref = self.document.get("questionnaire").get("reference")
        qn_name = qn_ref.split("/")[-1] if qn_ref else None
        qn = Questionnaire.find_by_name(name=qn_name)

        qnr['contained'] = [qn.as_fhir()]
        return qnr

QNR = namedtuple('QNR', [
    'qnr_id', 'qb_id', 'iteration', 'status', 'instrument', 'authored',
    'encounter_id'])


class QNR_results(object):
    """API for QuestionnaireResponses for a user"""

    def __init__(
            self, user, research_study_id, qb_ids=None, qb_iteration=None,
            ignore_iteration=False):
        """Optionally include qb_id and qb_iteration to limit

        :param user: subject in question
        :param research_study_id: study being processed
        :param qb_ids: include as list to filter results to only qb_id(s)
        :param qb_iteration: used only when qb_id is set and ignore_iteration
         is NOT set
        :param ignore_iteration: used in combination with qb_id to filter
         results on the given questionnaire bank, but ignore the iteration.

        """
        self.user = user
        self.research_study_id = research_study_id
        self.qb_ids = qb_ids
        self.qb_iteration = qb_iteration
        self.ignore_iteration = ignore_iteration
        self._qnrs = None

    @property
    def qnrs(self):
        """Return cached qnrs or query first time"""
        if self._qnrs is not None:
            return self._qnrs

        query = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == self.user.id).with_entities(
            QuestionnaireResponse.id,
            QuestionnaireResponse.questionnaire_bank_id,
            QuestionnaireResponse.qb_iteration,
            QuestionnaireResponse.status,
            QuestionnaireResponse.document[
                ('questionnaire', 'reference')].label('instrument_id'),
            QuestionnaireResponse.document['authored'].label('authored'),
            QuestionnaireResponse.encounter_id).order_by(
            QuestionnaireResponse.document['authored'])
        if self.qb_ids:
            query = query.filter(
                QuestionnaireResponse.questionnaire_bank_id.in_(self.qb_ids))
            if not self.ignore_iteration:
                query = query.filter(
                    QuestionnaireResponse.qb_iteration == self.qb_iteration)
        self._qnrs = []
        prev_auth = None
        for qnr in query:
            # Cheaper to toss those from the wrong research study now
            instrument = qnr.instrument_id.split('/')[-1]
            research_study_id = research_study_id_from_questionnaire(
                instrument)
            if research_study_id != self.research_study_id:
                continue

            # confirm a timezone extension in authored didn't foil the sort
            auth_datetime = FHIR_datetime.parse(qnr.authored)
            if prev_auth and prev_auth > auth_datetime:
                message = (
                    "String sort order for"
                    " `questionnaire_response.document['authored']`"
                    " differs from datetime sort.  Review authored values"
                    f" for user {self.user.id}")
                current_app.logger.error(message)
            prev_auth = auth_datetime

            self._qnrs.append(QNR(
                qnr_id=qnr.id,
                qb_id=qnr.questionnaire_bank_id,
                iteration=qnr.qb_iteration,
                status=qnr.status,
                instrument=instrument,
                authored=auth_datetime,
                encounter_id=qnr.encounter_id))
        return self._qnrs

    def assign_qb_relationships(self, qb_generator):
        """Associate any QNRs with respective qbs

        Typically, done at time of QNR POST - however occasionally events
        force a renewed lookup of QNR -> QB association.

        """
        from .qb_timeline import calc_and_adjust_expired, calc_and_adjust_start

        if self.qb_ids:
            raise ValueError(
                "Can't associate results when restricted to single QB")

        qbs = [
            qb for qb in
            qb_generator(self.user, research_study_id=self.research_study_id)]
        indef_qbs = [
            qb for qb in
            qb_generator(
                self.user, research_study_id=self.research_study_id,
                classification="indefinite")]

        td = trigger_date(
            user=self.user, research_study_id=self.research_study_id)
        old_td, withdrawal_date = consent_withdrawal_dates(
            self.user, research_study_id=self.research_study_id)
        if not td and old_td and withdrawal_date:
            td = old_td

        def qbd_accessor(as_of_date, classification, instrument):
            """Simplified qbd lookup consults only assigned qbs"""
            if classification == 'indefinite':
                container = indef_qbs
            else:
                container = qbs

            # Loop until date matching qb found.  Occasionally
            # QBs overlap, such as during a protocol change.  Look
            # ahead one beyond match, preferring second if two fit.
            match, laps = None, 0
            for qbd in container:
                if match:
                    # due to the introduction of additional visits
                    # from protocol changes, i.e. month 33 and 39 in v5
                    # once a match is found allow look ahead for 3 QBs,
                    # looking for a subsequent overlapping match.
                    # such a protocol change generates the ordered array
                    # [..., month36-v3, month33-v5, month36-v5, ...]
                    laps += 1
                    if laps > 3:
                        return match
                qb_start = calc_and_adjust_start(
                    user=self.user,
                    research_study_id=self.research_study_id,
                    qbd=qbd,
                    initial_trigger=td)
                qb_expired = calc_and_adjust_expired(
                    user=self.user,
                    research_study_id=self.research_study_id,
                    qbd=qbd,
                    initial_trigger=td)
                if as_of_date < qb_start:
                    continue
                if qb_start <= as_of_date < qb_expired:
                    if not match:
                        # first match found.  retain as the likely fit
                        match = qbd
                    else:
                        # second hit only happens with overlapping QBs and is
                        # as far as we look.  if the instrument only fits in
                        # one, return it - otherwise, prefer the second.
                        these_qs = [
                            q.name for q in
                            qbd.questionnaire_bank.questionnaires]
                        match_qs = [
                            q.name for q in
                            match.questionnaire_bank.questionnaires]

                        if instrument in these_qs:
                            return qbd
                        if instrument in match_qs:
                            return match
                        return qbd

            return match

        # typically triggered from updating task job - use system
        # as acting user in audits, if no current user is available
        acting_user = None
        if has_request_context():
            acting_user = current_user()
        if not acting_user:
            acting_user = User.query.filter_by(email='__system__').first()
        for qnr in self.qnrs:
            QuestionnaireResponse.query.get(
                qnr.qnr_id).assign_qb_relationship(
                acting_user_id=acting_user.id, qbd_accessor=qbd_accessor)
        db.session.commit()

        # Force fresh lookup on next access
        self._qnrs = None

    def qnrs_missing_qb_association(self):
        """Returns true if any QNRs exist without qb associations

        Business rules mandate purging qnr->qb association following
        events such as a change of consent date.  This method can be
        used to determine if qnr->qb association lookup may be required.

        NB - it can be legitimate for QNRs to never have a QB association,
        such as systems that don't define QBs for all assessments or those
        taken prior to a new trigger date.

        :returns: True if at least one QNR exists for the user missing qb_id

        """
        associated = [qnr for qnr in self.qnrs if qnr.qb_id is not None]
        return len(self.qnrs) != len(associated)

    def reassign_qb_association(self, existing, desired):
        """Update any contained QNRs from existing QB to desired"""
        changed = False
        for qnr in self.qnrs:
            if (
                    qnr.qb_id == existing['qb_id'] and
                    qnr.iteration == existing['iteration']):
                changed = True
                actual_qnr = QuestionnaireResponse.query.get(qnr.qnr_id)
                actual_qnr.questionnaire_bank_id = desired['qb_id']
                actual_qnr.qb_iteration = desired['iteration']
        if changed:
            db.session.commit()
            self._qnrs = None
        return changed

    def authored_during_period(self, start, end, restrict_to_instruments=None):
        """Return the ordered list of QNRs with authored in [start, end)"""
        results = []
        for qnr in self.qnrs:
            if qnr.authored < start:
                continue
            if qnr.authored >= end:
                return results
            if (restrict_to_instruments and
                    qnr.instrument not in restrict_to_instruments):
                continue
            results.append(qnr)
        return results

    def earliest_result(self, qb_id, iteration):
        """Returns timestamp of earliest result for given params, or None"""
        for qnr in self.qnrs:
            if (qnr.qb_id == qb_id and
                    qnr.iteration == iteration):
                return qnr.authored

    def entry_method(self):
        """Returns most common entry method over set of QNRs in this visit"""
        found = defaultdict(int)
        for qnr in self.qnrs:
            encounter = Encounter.query.get(qnr.encounter_id)
            if encounter.auth_method == 'staff_authenticated':
                found['staff_authenticated'] += 1
            elif encounter.type and len(encounter.type):
                for item in encounter.type:
                    found[item.code] += 1
            else:
                found['online'] += 1

        if not found:
            return None

        # return only one, namely the most frequent
        # if not all were the same as most frequent, include ratio
        max_key = max(found, key=lambda key: found[key])
        show_ratio = False
        if show_ratio:
            total_found = sum(value for value in found.values())
            if found[max_key] != total_found:
                return f"{max_key} {found[max_key]}:{total_found}"
        return max_key

    def required_qs(self, qb_id):
        """Return required list (order counts) of Questionnaires for QB"""
        from .questionnaire_bank import QuestionnaireBank  # avoid import cyc.
        qb = QuestionnaireBank.query.get(qb_id)
        return [q.name for q in qb.questionnaires]

    def completed_qs(self, qb_id, iteration):
        """Return set of completed Questionnaire results for given QB"""
        return {qnr.instrument for qnr in self.qnrs if
                qnr.qb_id == qb_id
                and qnr.iteration == iteration
                and qnr.status == "completed"}

    def partial_qs(self, qb_id, iteration):
        """Return set of partial Questionnaire results for given QB"""
        return {qnr.instrument for qnr in self.qnrs if
                qnr.qb_id == qb_id
                and qnr.iteration == iteration
                and qnr.status == "in-progress"}

    def completed_date(self, qb_id, iteration):
        """Returns timestamp when named QB was completed, or None"""
        required = set(self.required_qs(qb_id))
        have = self.completed_qs(qb_id=qb_id, iteration=iteration)
        if required - have:
            # incomplete set
            return None
        # Return time when last completed in required came in
        germane = [qnr for qnr in self.qnrs if
                   qnr.qb_id == qb_id
                   and qnr.iteration == iteration
                   and qnr.status == "completed"]
        for item in germane:
            if item.instrument in required:
                required.remove(item.instrument)
            if not required:
                return item.authored
        raise RuntimeError("should have found authored for all required")


class QNR_indef_results(QNR_results):
    """Specialized for indefinite QB

    Indefinite is special, in that once done - don't offer again, even if
    the protocol changes.

    """

    def __init__(self, user, research_study_id, qb_id):
        # define unused attributes from base class:
        self.qb_ids = None
        self.qb_iteration = None
        self.ignore_iteration = None

        self.user = user
        self.research_study_id = research_study_id
        # qb_id is the current indef qb - irrelevant if done in previous
        self.qb_id = qb_id

        query = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == user.id).join(
            QuestionnaireBank).filter(
            QuestionnaireResponse.questionnaire_bank_id ==
            QuestionnaireBank.id).filter(
            QuestionnaireBank.classification == 'indefinite'
        ).with_entities(
            QuestionnaireResponse.id,
            QuestionnaireResponse.questionnaire_bank_id,
            QuestionnaireResponse.qb_iteration,
            QuestionnaireResponse.status,
            QuestionnaireResponse.document[
                ('questionnaire', 'reference')].label('instrument_id'),
            QuestionnaireResponse.document['authored'].label('authored'),
            QuestionnaireResponse.encounter_id).order_by(
            QuestionnaireResponse.document['authored'])

        self._qnrs = []
        for qnr in query:
            self._qnrs.append(QNR(
                qnr_id=qnr.id,
                qb_id=qnr.questionnaire_bank_id,
                iteration=qnr.qb_iteration,
                status=qnr.status,
                instrument=qnr.instrument_id.split('/')[-1],
                authored=FHIR_datetime.parse(qnr.authored),
                encounter_id=qnr.encounter_id))

    def completed_qs(self, qb_id, iteration):
        """Return set of completed Questionnaire results for Indefinite"""
        # ignore the qb_id - as prior protocol versions picked up also count
        return {
            qnr.instrument for qnr in self.qnrs
            if qnr.status == "completed"}

    def partial_qs(self, qb_id, iteration):
        """Return set of partial Questionnaire results for Indefinite"""
        # ignore the qb_id - as prior protocol versions picked up also count
        return {
            qnr.instrument for qnr in self.qnrs
            if qnr.status == "in-progress"}

    def required_qs(self, qb_id):
        """Return required list of Questionnaires for QB"""
        # if user completed or started an indefinite questionnaire on prior
        # RP, potentially with different name, report that as only required
        # given indefinite special handling
        completed = self.completed_qs(qb_id, None)
        if completed:
            return [q for q in completed]

        partial = self.partial_qs(qb_id, None)
        if partial:
            return [q for q in partial]

        from .questionnaire_bank import QuestionnaireBank  # avoid import cyc.
        qb = QuestionnaireBank.query.get(qb_id)
        return [q.name for q in qb.questionnaires]


def aggregate_responses(
        instrument_ids, current_user, research_study_id, patch_dstu2=False,
        ignore_qb_requirement=False, celery_task=None, patient_ids=None):
    """Build a bundle of QuestionnaireResponses

    :param instrument_ids: list of instrument_ids to restrict results to
    :param current_user: user making request, necessary to restrict results
        to list of patients the current_user has permission to see
    :param research_study_id: study being processed
    :param patch_dstu2: set to make bundle DSTU2 compliant
    :param ignore_qb_requirement: set to include all questionnaire responses
    :param celery_task: if defined, send occasional progress updates
    :param patient_ids: if defined, limit result set to given patient list

    NB: research_study_id not used to filter / restrict query set, but rather
    for lookup of visit name.  Use instrument_ids to restrict query set.
    """
    from .qb_timeline import qb_status_visit_name  # avoid cycle

    # Gather up the patient IDs for whom current user has 'view' permission
    user_ids = patients_query(
        current_user,
        include_test_role=False,
        filter_by_ids=patient_ids,
    ).with_entities(User.id)

    annotated_questionnaire_responses = []
    questionnaire_responses = QuestionnaireResponse.query.filter(
        QuestionnaireResponse.subject_id.in_(user_ids)).order_by(
        QuestionnaireResponse.document['authored'].desc())

    # TN-3250, don't include QNRs without assigned visits, i.e. qb_id > 0
    if not ignore_qb_requirement:
        questionnaire_responses = questionnaire_responses.filter(
            QuestionnaireResponse.questionnaire_bank_id > 0)

    if instrument_ids:
        instrument_filters = (
            QuestionnaireResponse.document[
                ("questionnaire", "reference")
            ].astext.endswith(instrument_id)
            for instrument_id in instrument_ids
        )
        questionnaire_responses = questionnaire_responses.filter(
            or_(*instrument_filters))

    patient_fields = ("careProvider", "identifier")
    system_filter = current_app.config.get('REPORTING_IDENTIFIER_SYSTEMS')
    if celery_task:
        current, total = 0, questionnaire_responses.count()

    for questionnaire_response in questionnaire_responses:
        document = questionnaire_response.document_answered.copy()
        subject = questionnaire_response.subject
        encounter = questionnaire_response.encounter
        encounter_fhir = encounter.as_fhir()
        document["encounter"] = encounter_fhir

        document["subject"] = {
            k: v for k, v in subject.as_fhir().items() if k in patient_fields
        }

        if subject.organizations:
            providers = []
            for org in subject.organizations:
                org_ref = Reference.organization(org.id).as_fhir()
                identifiers = [i.as_fhir() for i in org.identifiers if
                               i.system in system_filter]
                if identifiers:
                    org_ref['identifier'] = identifiers
                providers.append(org_ref)
            document["subject"]["careProvider"] = providers

        qb_status = qb_status_visit_name(
            subject.id,
            research_study_id,
            FHIR_datetime.parse(questionnaire_response.document['authored']))
        document["timepoint"] = qb_status['visit_name']

        # Hack: add missing "resource" wrapper for DTSU2 compliance
        # Remove when all interventions compliant
        if patch_dstu2:
            document = {
                'resource': document,
                # Todo: return URL to individual QuestionnaireResponse resource
                'fullUrl': url_for(
                    'assessment_engine_api.assessment',
                    patient_id=subject.id,
                    _external=True,
                ),
            }

        annotated_questionnaire_responses.append(document)

        if celery_task:
            current += 1
            if current % 25 == 0:
                celery_task.update_state(
                    state='PROGRESS',
                    meta={'current': current, 'total': total})

    return bundle_results(elements=annotated_questionnaire_responses)


def qnr_document_id(
        subject_id, questionnaire_bank_id, questionnaire_name, iteration,
        status):
    """Return document['identifier'] for matching QuestionnaireResponse

    Using the given filter data to look for a matching QuestionnaireResponse.
    Expecting to find exactly one, or raises NoResultFound

    :return: the document identifier value, typically a string

    """
    qnr = QuestionnaireResponse.query.filter(
        QuestionnaireResponse.status == status).filter(
        QuestionnaireResponse.subject_id == subject_id).filter(
        QuestionnaireResponse.document[
            ('questionnaire', 'reference')
        ].astext.endswith(questionnaire_name)).filter(
        QuestionnaireResponse.questionnaire_bank_id ==
        questionnaire_bank_id).with_entities(
        QuestionnaireResponse.document[(
            'identifier', 'value')])
    if iteration is not None:
        qnr = qnr.filter(QuestionnaireResponse.qb_iteration == iteration)
    else:
        qnr = qnr.filter(QuestionnaireResponse.qb_iteration.is_(None))

    # Should always get exactly one.
    # Raise attention via error log if not, but continue (TN-3109)
    try:
        return qnr.one()[0]
    except MultipleResultsFound:
        current_app.logger.error(
            f"Multiple {status} QNRs found for user {subject_id} on qb_id {questionnaire_bank_id}")
        return qnr.first()[0]


def consolidate_answer_pairs(answers):
    """
    Merge paired answers (code and corresponding text) into single
        row/answer

    Codes are the preferred way of referring to options but option text
        (at the time of administration) may be submitted alongside coded
        answers for ease of display
    """
    last_answer = None
    for answer in answers:
        # answer pair detected, only yield coded value
        if 'valueCoding' in answer and last_answer and 'valueString' in last_answer:
            answer['valueCoding']['text'] = last_answer['valueString']
            last_answer = None
            yield answer
            continue

        # no pair, yield last answer before storing another
        if last_answer:
            yield last_answer

        # store answer and check for pair on next iteration
        if 'valueString' in answer:
            last_answer = answer
            continue

        # not valueString, yield immediatly
        yield answer

    # yield leftover unpaired valueString
    if last_answer:
        yield last_answer

qnr_csv_column_headers = (
    'identifier',
    'status',
    'study_id',
    'site_id',
    'site_name',
    'truenth_subject_id',
    'author_id',
    'author_role',
    'entry_method',
    'authored',
    'timepoint',
    'instrument',
    'question_code',
    'answer_code',
    'option_text',
    'other_text',
)


def generate_qnr_csv(qnr_bundle):
    """Generate a CSV from a bundle of QuestionnaireResponses"""

    class HTMLStripper(HTMLParser):
        """Subclass of HTMLParser for stripping HTML tags"""

        def __init__(self):
            self.reset()
            self.strict = False
            self.convert_charrefs = True
            self.fed = []

        def handle_data(self, data):
            self.fed.append(data)

        def get_data(self):
            return ' '.join(self.fed)

    def strip_tags(html):
        """Strip HTML tags from strings. Inserts whitespace if necessary."""

        if html is None:
            return
        s = HTMLStripper()
        s.feed(html)
        stripped = s.get_data()
        # Remove extra spaces
        return ' '.join(filter(None, stripped.split(' ')))

    def get_identifier(id_list, **kwargs):
        """Return first identifier object matching kwargs"""
        for identifier in id_list:
            for k, v in kwargs.items():
                if identifier.get(k) != v:
                    break
            else:
                return identifier['value']
        return None

    def get_site(qnr_data):
        """Return (external id, name) of first organization, else Nones"""
        try:
            provider = qnr_data['subject']['careProvider'][0]
            org_name = provider['display']
            if 'identifier' in provider:
                id_value = provider['identifier'][0]['value']
            else:
                id_value = None
            return id_value, org_name
        except (KeyError, IndexError):
            return None, None

    def entry_method(row_data, qnr_data):
        # Todo: replace with EC.PAPER CodeableConcept
        if (
                'type' in qnr_data['encounter'] and
                'paper' in (c.get('code') for c in
                            qnr_data['encounter']['type'])
        ):
            return 'enter manually - paper'
        if row_data.get('truenth_subject_id') == row_data.get('author_id'):
            return 'online'
        else:
            return 'enter manually - interview assisted'

    def author_role(row_data, qnr_data):
        if row_data.get('truenth_subject_id') == row_data.get('author_id'):
            return 'Subject'
        else:
            return 'Site Resource'

    for qnr in qnr_bundle['entry']:
        site_id, site_name = get_site(qnr)
        row_data = {
            'identifier': (
                qnr['identifier']['value'] if 'identifier' in qnr else None),
            'status': qnr['status'],
            'truenth_subject_id': get_identifier(
                qnr['subject']['identifier'],
                use='official'
            ),
            'author_id': (
                qnr['author']['reference'].split('/')[-1]
                if 'author' in qnr else None),
            'site_id': site_id,
            'site_name': site_name,
            # Todo: correctly pick external study of interest
            'study_id': get_identifier(
                qnr['subject']['identifier'],
                system=TRUENTH_EXTERNAL_STUDY_SYSTEM
            ),
            'authored': qnr['authored'],
            'timepoint': qnr['timepoint'],
            'instrument': qnr['questionnaire']['reference'].split('/')[-1],
        }
        row_data.update({
            'entry_method': entry_method(row_data, qnr),
            'author_role': author_role(row_data, qnr),
        })
        for question in qnr['group']['question']:
            row_data['question_code'] = question['linkId']
            for answer in consolidate_answer_pairs(
                    question['answer']) or ({},):

                # Clear keys potentially added on previous loop
                row_data.pop('answer_code', None)
                row_data.pop('option_text', None)
                row_data.pop('other_text', None)

                if answer:
                    # Use first value of answer (most are single-entry dicts)
                    if list(answer.keys())[0] != 'valueCoding':
                        row_data['other_text'] = list(answer.values())[0]

                    # ...unless nested code (ie valueCode)
                    else:
                        row_data['answer_code'] = answer['valueCoding']['code']

                        # Add supplementary text added earlier
                        # Todo: lookup option text in stored Questionnaire
                        row_data['option_text'] = strip_tags(
                            answer['valueCoding'].get('text', None))
                yield {k: v for k, v in row_data.items() if v is not None}


def first_last_like_qnr(qnr):
    """Specialized lookup function to return similar QNRs

    As clients need QNRs spanning baseline and recurring, can't simply locate
    on qb_id alone.  Look up "similar" based on the QNR's QB, the QB's
    questionnaire, and other QBs with the same questionnaire.  The resulting
    set of questionnaire banks and the qnr.subject_id are used to look for
    "similar" results.

    :param qnr: reference QNR - look for first and most recent QNRs similar
      to the one provided.  That is owned by the same subject and QBs
      containing the same questionnaire.

    :return: tuple(first, last) of like QNRs, if found.  One or both may be
      None if not found.

    """
    user = User.query.get(qnr.subject_id)
    rs_id = qnr.questionnaire_bank.research_study_id
    qbq = qnr.questionnaire_bank.questionnaires
    if not qbq or len(qbq) > 1:
        # TODO raise once beyond initial testing, for now, return nones
        current_app.logger.warning(
            "No questionnaires associated w/ QNR - assume test data")
        return None, None
        """raise ValueError(
            "supporting exactly one questionnaire in QNR->QB within"
            " `first_last_like_qnr()`")"""
    q_id = qbq[0].questionnaire_id

    query = QuestionnaireBank.query.join(
        QuestionnaireBankQuestionnaire).filter(
        QuestionnaireBank.id ==
        QuestionnaireBankQuestionnaire.questionnaire_bank_id).filter(
        QuestionnaireBankQuestionnaire.questionnaire_id == q_id).with_entities(
        QuestionnaireBank.id)
    qb_ids = [qb.id for qb in query]
    if not qb_ids:
        raise ValueError("no matching qbs found!")

    postedQNRs = QNR_results(
        user,
        research_study_id=rs_id,
        qb_ids=qb_ids,
        ignore_iteration=True)

    initial, last = None, None
    for q in postedQNRs.qnrs:
        if q.status != 'completed':
            continue
        if q.qnr_id == qnr.id:
            # ordered list, made it to current
            break
        if not initial:
            initial = q
            continue
        last = q
    return initial, last


def capture_patient_state(patient_id):
    """Call to capture QBT and QNR state for patient, used for before/after"""
    from .qb_timeline import QBT
    qnrs = QuestionnaireResponse.qnr_state(patient_id)
    tl = QBT.timeline_state(patient_id)
    return {'qnrs': qnrs, 'timeline': tl}


def present_before_after_state(user_id, external_study_id, before_state):
    from .qb_timeline import QBT
    from ..dict_tools import dict_compare
    after_qnrs = QuestionnaireResponse.qnr_state(user_id)
    after_timeline = QBT.timeline_state(user_id)
    qnrs_lost_reference = []
    any_change_noted = False

    def visit_from_timeline(qb_name, qb_iteration, timeline_results):
        """timeline results have computed visit name - quick lookup"""
        for visit, name, iteration in timeline_results.values():
            if qb_name == name and qb_iteration == iteration:
                return visit
        raise ValueError(f"no visit found for {qb_name}, {qb_iteration}")

    # Compare results
    added_q, removed_q, modified_q, same = dict_compare(
        after_qnrs, before_state['qnrs'])
    assert not added_q
    assert not removed_q

    added_t, removed_t, modified_t, same = dict_compare(
        after_timeline, before_state['timeline'])

    if any((added_t, removed_t, modified_t, modified_q)):
        any_change_noted = True
        print(f"\nPatient {user_id} ({external_study_id}):")
    if modified_q:
        any_change_noted = True
        print("\tModified QNRs (old, new)")
        for mod in sorted(modified_q):
            print(f"\t\t{mod} {modified_q[mod][1]} ==>"
                  f" {modified_q[mod][0]}")
            # If the QNR previously had a reference QB and since
            # lost it, capture for reporting.
            if (
                    modified_q[mod][1][0] != "none of the above" and
                    modified_q[mod][0][0] == "none of the above"):
                visit_name = visit_from_timeline(
                    modified_q[mod][1][0],
                    modified_q[mod][1][1],
                    before_state["timeline"])
                qnrs_lost_reference.append((visit_name, modified_q[mod][1][2]))
    if added_t:
        any_change_noted = True
        print("\tAdditional timeline rows:")
        for item in sorted(added_t):
            print(f"\t\t{item} {after_timeline[item]}")
    if removed_t:
        any_change_noted = True
        print("\tRemoved timeline rows:")
        for item in sorted(removed_t):
            print(
                f"\t\t{item} "
                f"{before_state['timeline'][item]}")
    if modified_t:
        any_change_noted = True
        print(f"\tModified timeline rows: (old, new)")
        for item in sorted(modified_t):
            print(f"\t\t{item}")
            print(f"\t\t\t{modified_t[item][1]} ==> {modified_t[item][0]}")

    return after_qnrs, after_timeline, qnrs_lost_reference, any_change_noted
