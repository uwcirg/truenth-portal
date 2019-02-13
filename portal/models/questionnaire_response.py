from collections import namedtuple
from html.parser import HTMLParser
import json

from flask import current_app, url_for
from past.builtins import basestring
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import ENUM, JSONB

from ..database import db
from ..date_tools import FHIR_datetime
from ..system_uri import TRUENTH_EXTERNAL_STUDY_SYSTEM
from .fhir import bundle_results
from .organization import OrgTree
from .reference import Reference


class QuestionnaireResponse(db.Model):

    def default_status(context):
        return context.current_parameters['document']['status']

    def default_authored(context):
        return FHIR_datetime.parse(
            context.current_parameters['document']['authored'])

    __tablename__ = 'questionnaire_responses'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    subject = db.relationship("User", back_populates="questionnaire_responses")
    document = db.Column(JSONB)
    encounter_id = db.Column(
        db.ForeignKey('encounters.id', name='qr_encounter_id_fk'),
        nullable=False)
    questionnaire_bank_id = db.Column(
        db.ForeignKey('questionnaire_banks.id'), nullable=True)
    qb_iteration = db.Column(db.Integer(), nullable=True)

    encounter = db.relationship("Encounter", cascade='delete')
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

    authored = db.Column(
        db.DateTime,
        default=default_authored
    )

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "QuestionnaireResponse {0.id} for user {0.subject_id} " \
               "{0.status} {0.authored}".format(self)

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
        return found.order_by(QuestionnaireResponse.id.desc()).all()

QNR = namedtuple(
    'QNR', ['qb_id', 'iteration', 'status', 'instrument', 'authored'])


class QNR_results(object):
    """API for QuestionnaireResponses for a user"""

    def __init__(self, user, qb_id=None, qb_iteration=None):
        """Optionally include qb_id, qb_iteration and recur to limit"""
        self.user = user
        query = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == user.id).with_entities(
            QuestionnaireResponse.questionnaire_bank_id,
            QuestionnaireResponse.qb_iteration,
            QuestionnaireResponse.status,
            QuestionnaireResponse.document[
                ('questionnaire', 'reference')].label('instrument_id'),
            QuestionnaireResponse.authored).order_by(
            QuestionnaireResponse.authored)
        if qb_id:
            query = query.filter(
                QuestionnaireResponse.questionnaire_bank_id == qb_id).filter(
                QuestionnaireResponse.qb_iteration == qb_iteration)
        self.qnrs = []
        for qnr in query:
            self.qnrs.append(QNR(
                qb_id=qnr.questionnaire_bank_id,
                iteration=qnr.qb_iteration,
                status=qnr.status,
                instrument=qnr.instrument_id.split('/')[-1],
                authored=qnr.authored))

    def earliest_result(self, qb_id, iteration):
        """Returns timestamp of earliest result for given params, or None"""
        for qnr in self.qnrs:
            if (qnr.qb_id == qb_id and
                    qnr.iteration == iteration):
                return qnr.authored

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
    """Specialized for indefinite QB"""

    def __init__(self, user, qb_id):
        self.user = user
        query = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == user.id).filter(
            QuestionnaireResponse.questionnaire_bank_id == qb_id
        ).with_entities(
            QuestionnaireResponse.questionnaire_bank_id,
            QuestionnaireResponse.qb_iteration,
            QuestionnaireResponse.status,
            QuestionnaireResponse.document[
                ('questionnaire', 'reference')].label('instrument_id'),
            QuestionnaireResponse.authored).order_by(
            QuestionnaireResponse.authored)

        self.qnrs = []
        for qnr in query:
            self.qnrs.append(QNR(
                qb_id=qnr.questionnaire_bank_id,
                iteration=qnr.qb_iteration,
                status=qnr.status,
                instrument=qnr.instrument_id.split('/')[-1],
                authored=qnr.authored))


def aggregate_responses(instrument_ids, current_user, patch_dstu2=False):
    """Build a bundle of QuestionnaireResponses

    :param instrument_ids: list of instrument_ids to restrict results to
    :param current_user: user making request, necessary to restrict results
        to list of patients the current_user has permission to see

    """
    from .qb_timeline import qb_status_visit_name  # avoid cycle

    # Gather up the patient IDs for whom current user has 'view' permission
    user_ids = OrgTree().visible_patients(current_user)

    annotated_questionnaire_responses = []
    questionnaire_responses = QuestionnaireResponse.query.filter(
        QuestionnaireResponse.subject_id.in_(user_ids)).order_by(
        QuestionnaireResponse.authored.desc())

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
    for questionnaire_response in questionnaire_responses:
        document = questionnaire_response.document.copy()
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

        _, timepoint = qb_status_visit_name(subject.id, encounter.start_time)
        document["timepoint"] = timepoint

        # Hack: add missing "resource" wrapper for DTSU2 compliance
        # Remove when all interventions compliant
        if patch_dstu2:
            document = {
                'resource': document,
                # Todo: return URL to individual QuestionnaireResponse resource
                'fullUrl': url_for(
                    '.assessment',
                    patient_id=subject.id,
                    _external=True,
                ),
            }

        annotated_questionnaire_responses.append(document)

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

    return qnr.one()[0]


def generate_qnr_csv(qnr_bundle):
    """Generate a CSV from a bundle of QuestionnaireResponses"""

    csv_null_value = r"\N"

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

    def consolidate_answer_pairs(answers):
        """
        Merge paired answers (code and corresponding text) into single
            row/answer

        Codes are the preferred way of referring to options but option text
            (at the time of administration) may be submitted alongside coded
            answers for ease of display
        """

        answer_types = [a.keys()[0] for a in answers]

        # Exit early if assumptions not met
        if (
            len(answers) % 2 or
            answer_types.count('valueCoding')
                != answer_types.count('valueString')
        ):
            return answers

        filtered_answers = []
        for pair in zip(*[iter(answers)] * 2):
            # Sort so first pair is always valueCoding
            pair = sorted(pair, key=lambda k: k.keys()[0])
            coded_answer, string_answer = pair

            coded_answer['valueCoding']['text'] = string_answer['valueString']

            filtered_answers.append(coded_answer)

        return filtered_answers

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
        if (
            row_data.get('truenth_subject_id') == row_data.get('author_id') or
            (
                'type' in qnr_data['encounter'] and
                'paper' in
                (c.get('code') for c in qnr_data['encounter']['type'])
            )
        ):
            return 'Subject'
        else:
            return 'Site Resource'

    columns = (
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

    yield ','.join('"' + column + '"' for column in columns) + '\n'
    for qnr in qnr_bundle['entry']:
        site_id, site_name = get_site(qnr)
        row_data = {
            'identifier': qnr['identifier']['value'],
            'status': qnr['status'],
            'truenth_subject_id': get_identifier(
                qnr['subject']['identifier'],
                use='official'
            ),
            'author_id': qnr['author']['reference'].split('/')[-1],
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
            row_data.update({
                'question_code': question['linkId'],
                'answer_code': None,
                'option_text': None,
                'other_text': None,
            })

            answers = consolidate_answer_pairs(question['answer']) or ({},)

            for answer in answers:
                if answer:
                    # Use first value of answer (most are single-entry dicts)
                    answer_data = {'other_text': answer.values()[0]}

                    # ...unless nested code (ie valueCode)
                    if answer.keys()[0] == 'valueCoding':
                        answer_data.update({
                            'answer_code': answer['valueCoding']['code'],

                            # Add supplementary text added earlier
                            # Todo: lookup option text in stored Questionnaire
                            'option_text': strip_tags(
                                answer['valueCoding'].get('text', None)),
                            'other_text': None,
                        })
                    row_data.update(answer_data)

                row = []
                for column_name in columns:
                    column = row_data.get(column_name)
                    column = csv_null_value if column is None else column

                    # Handle JSON column escaping/enclosing
                    if not isinstance(column, basestring):
                        column = json.dumps(column).replace('"', '""')
                    row.append('"' + column + '"')

                yield ','.join(row) + '\n'
