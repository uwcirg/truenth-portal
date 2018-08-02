"""Model classes for retaining FHIR data"""
from datetime import datetime
from html.parser import HTMLParser
import json

from flask import abort, current_app, url_for
from past.builtins import basestring
import requests
from sqlalchemy import UniqueConstraint, or_
from sqlalchemy.dialects.postgresql import ENUM, JSONB

from ..database import db
from ..date_tools import FHIR_datetime, as_fhir
from ..system_uri import (
    NHHD_291036,
    TRUENTH_CLINICAL_CODE_SYSTEM,
    TRUENTH_ENCOUNTER_CODE_SYSTEM,
    TRUENTH_EXTERNAL_STUDY_SYSTEM,
    TRUENTH_VALUESET,
)
from ..views.fhir import valueset_nhhd_291036
from .codeable_concept import CodeableConcept
from .coding import Coding
from .lazy import lazyprop
from .locale import LocaleConstants
from .organization import OrgTree
from .performer import Performer
from .reference import Reference

""" TrueNTH Clinical Codes """


class ClinicalConstants(object):

    def __iter__(self):
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            yield getattr(self, attr)

    @lazyprop
    def BIOPSY(self):
        coding = Coding(
            system=TRUENTH_CLINICAL_CODE_SYSTEM,
            code='111',
            display='biopsy',
        ).add_if_not_found(True)
        cc = CodeableConcept(codings=[coding, ]).add_if_not_found(True)
        assert coding in cc.codings
        return cc

    @lazyprop
    def PCaDIAG(self):
        coding = Coding(
            system=TRUENTH_CLINICAL_CODE_SYSTEM,
            code='121',
            display='PCa diagnosis',
        ).add_if_not_found(True)
        cc = CodeableConcept(codings=[coding, ]).add_if_not_found(True)
        assert coding in cc.codings
        return cc

    @lazyprop
    def PCaLocalized(self):
        coding = Coding(
            system=TRUENTH_CLINICAL_CODE_SYSTEM,
            code='141',
            display='PCa localized diagnosis',
        ).add_if_not_found(True)
        cc = CodeableConcept(codings=[coding, ]).add_if_not_found(True)
        assert coding in cc.codings
        return cc

    @lazyprop
    def TRUE_VALUE(self):
        value_quantity = ValueQuantity(
            value='true', units='boolean').add_if_not_found(True)
        return value_quantity

    @lazyprop
    def FALSE_VALUE(self):
        value_quantity = ValueQuantity(
            value='false', units='boolean').add_if_not_found(True)
        return value_quantity


CC = ClinicalConstants()


class EncounterConstants(object):
    """ TrueNTH Encounter type Codes
    See http://www.hl7.org/FHIR/encounter-definitions.html#Encounter.type
    """

    def __iter__(self):
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            yield getattr(self, attr)

    @lazyprop
    def PAPER(self):
        coding = Coding(
            system=TRUENTH_ENCOUNTER_CODE_SYSTEM,
            code='paper',
            display='Information collected on paper',
        ).add_if_not_found(True)
        cc = CodeableConcept(codings=[coding, ]).add_if_not_found(True)
        assert coding in cc.codings
        return cc

    @lazyprop
    def PHONE(self):
        coding = Coding(
            system=TRUENTH_ENCOUNTER_CODE_SYSTEM,
            code='phone',
            display='Information collected over telephone system',
        ).add_if_not_found(True)
        cc = CodeableConcept(codings=[coding, ]).add_if_not_found(True)
        assert coding in cc.codings
        return cc


EC = EncounterConstants()


class ValueQuantity(db.Model):
    __tablename__ = 'value_quantities'
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(80))
    units = db.Column(db.String(80))
    system = db.Column(db.String(255))
    code = db.Column(db.String(80))

    def __init__(self, value=None, units=None, system=None, code=None):
        self.value = value
        self.units = units
        self.system = system
        self.code = code
        if units == 'boolean':
            # If given an integer (as some FHIR compliant libraries require
            # for Value Quantity), and the units are set to boolean, convert
            # based on classic truth value.
            try:
                self.value = int(value) != 0
            except (TypeError, ValueError) as e:
                if value is None or isinstance(value, basestring):
                    pass
                else:
                    raise e

    def __str__(self):
        """Print friendly format for logging, etc."""
        components = ','.join(
            [str(x) for x in (self.value, self.units, self.system, self.code)
             if x is not None])
        return "ValueQuantity " + components

    def as_fhir(self):
        """Return self in JSON FHIR formatted string"""
        d = {}
        for i in ("value", "units", "system", "code"):
            if getattr(self, i):
                d[i] = getattr(self, i)
        return {"valueQuantity": d}

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, existing ValueQuantity (matches on
        value, units and system alone).  Populates self.id if found,
        adds to database first if not.

        """
        if self.id:
            return self

        lookup_value = self.value and str(self.value) or None
        match = self.query.filter_by(
            value=lookup_value, units=self.units, system=self.system).first()
        if not match:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        elif self is not match:
            self = db.session.merge(match)
        return self


class Observation(db.Model):
    __tablename__ = 'observations'
    id = db.Column(db.Integer, primary_key=True)
    issued = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(80))
    codeable_concept_id = db.Column(
        db.ForeignKey('codeable_concepts.id'), nullable=False)
    value_quantity_id = db.Column(
        db.ForeignKey('value_quantities.id'), nullable=False)
    codeable_concept = db.relationship(CodeableConcept, cascade="save-update")
    value_quantity = db.relationship(ValueQuantity)
    performers = db.relationship(
        'Performer', lazy='dynamic', cascade="save-update",
        secondary="observation_performers", backref=db.backref('observations'))

    def __str__(self):
        """Print friendly format for logging, etc."""
        at = ' at {0.issued}'.format(self) if self.issued else ''
        status = ' with status {0.status}'.format(self) if self.status else ''
        return (
            "Observation {0.codeable_concept} {0.value_quantity}{at}"
            "{status}".format(self, at=at, status=status))

    def as_fhir(self):
        """Return self in JSON FHIR formatted string"""
        fhir = {"resourceType": "Observation"}
        if self.issued:
            fhir['issued'] = as_fhir(self.issued)
        if self.status:
            fhir['status'] = self.status
        fhir['id'] = self.id
        fhir['code'] = self.codeable_concept.as_fhir()
        fhir.update(self.value_quantity.as_fhir())
        if self.performers:
            fhir['performer'] = [p.as_fhir() for p in self.performers]
        return fhir

    def update_from_fhir(self, data):
        if 'issued' in data:
            issued = FHIR_datetime.parse(data['issued']) if data[
                'issued'] else None
            setattr(self, 'issued', issued)
        if 'status' in data:
            setattr(self, 'status', data['status'])
        if 'performer' in data:
            for p in data['performer']:
                performer = Performer.from_fhir(p)
                self.performers.append(performer)
        if 'valueQuantity' in data:
            v = data['valueQuantity']
            current_v = self.value_quantity
            vq = ValueQuantity(
                value=v.get('value') if 'value' in v else current_v.value,
                units=v.get('units') or current_v.units,
                system=v.get('system') or current_v.system,
                code=v.get('code') or current_v.code).add_if_not_found(True)
            setattr(self, 'value_quantity_id', vq.id)
            setattr(self, 'value_quantity', vq)
        return self.as_fhir()

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for matching, existing Observation.
        Populates self.id if found, adds to database first if not.

        """
        if self.id:
            return self
        match_dict = {'issued': self.issued,
                      'status': self.status}
        if self.codeable_concept_id:
            match_dict['codeable_concept_id'] = self.codeable_concept_id
        if self.value_quantity_id:
            match_dict['value_quantity_id'] = self.value_quantity_id

        match = self.query.filter_by(**match_dict).first()
        if not match:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        elif self is not match:
            self = db.session.merge(match)
        return self


class UserObservation(db.Model):
    __tablename__ = 'user_observations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey(
        'users.id', ondelete='CASCADE'), nullable=False)
    observation_id = db.Column(
        db.ForeignKey('observations.id'), nullable=False)
    encounter_id = db.Column(
        db.ForeignKey('encounters.id', name='user_observation_encounter_id_fk'),
        nullable=False)
    audit_id = db.Column(db.ForeignKey('audit.id'), nullable=False)
    audit = db.relationship('Audit', cascade="save-update, delete")
    encounter = db.relationship('Encounter', cascade='delete')
    # There was a time when UserObservations were constrained to
    # one per (user_id, observation_id).  As history is important
    # and the same observation may be made twice, this constraint
    # was removed.


class UserIndigenous(db.Model):
    __tablename__ = 'user_indigenous'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    coding_id = db.Column(db.ForeignKey('codings.id'), nullable=False)

    __table_args__ = (UniqueConstraint(
        'user_id', 'coding_id', name='_indigenous_user_coding'),)


class UserEthnicity(db.Model):
    __tablename__ = 'user_ethnicities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    coding_id = db.Column(db.ForeignKey('codings.id'), nullable=False)

    __table_args__ = (UniqueConstraint(
        'user_id', 'coding_id', name='_ethnicity_user_coding'),)


class UserRace(db.Model):
    __tablename__ = 'user_races'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    coding_id = db.Column(db.ForeignKey('codings.id'), nullable=False)

    __table_args__ = (UniqueConstraint(
        'user_id', 'coding_id', name='_race_user_coding'),)


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


def aggregate_responses(instrument_ids, current_user, patch_dstu2=False):
    """Build a bundle of QuestionnaireResponses

    :param instrument_ids: list of instrument_ids to restrict results to
    :param current_user: user making request, necessary to restrict results
        to list of patients the current_user has permission to see

    """
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

    for questionnaire_response in questionnaire_responses:
        subject = questionnaire_response.subject
        encounter = questionnaire_response.encounter
        encounter_fhir = encounter.as_fhir()
        questionnaire_response.document["encounter"] = encounter_fhir

        questionnaire_response.document["subject"] = {
            k: v for k, v in subject.as_fhir().items() if k in patient_fields
        }

        if subject.organizations:
            questionnaire_response.document["subject"]["careProvider"] = [
                Reference.organization(org.id).as_fhir()
                for org in subject.organizations
            ]

        # Hack: add missing "resource" wrapper for DTSU2 compliance
        # Remove when all interventions compliant
        if patch_dstu2:
            questionnaire_response.document = {
                'resource': questionnaire_response.document,
                # Todo: return URL to individual QuestionnaireResponse resource
                'fullUrl': url_for(
                    '.assessment',
                    patient_id=questionnaire_response.subject_id,
                    _external=True,
                ),
            }

        annotated_questionnaire_responses.append(
            questionnaire_response.document)

    bundle = {
        'resourceType': 'Bundle',
        'updated': FHIR_datetime.now(),
        'total': len(annotated_questionnaire_responses),
        'type': 'searchset',
        'entry': annotated_questionnaire_responses,
    }

    return bundle


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

        def handle_data(self, d):
            self.fed.append(d)

        def get_data(self):
            return ' '.join(self.fed)

    def strip_tags(html):
        """Strip HTML tags from strings. Inserts replacement whitespace if necessary."""

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
        """Return name of first organization, else None"""
        try:
            return qnr_data['subject']['careProvider'][0]['display']
        except (KeyError, IndexError):
            return None

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
        'site_name',
        'truenth_subject_id',
        'author_id',
        'author_role',
        'entry_method',
        'authored',
        'instrument',
        'question_code',
        'answer_code',
        'option_text',
        'other_text',
    )

    yield ','.join('"' + column + '"' for column in columns) + '\n'
    for qnr in qnr_bundle['entry']:
        row_data = {
            'identifier': qnr['identifier']['value'],
            'status': qnr['status'],
            'truenth_subject_id': get_identifier(
                qnr['subject']['identifier'],
                use='official'
            ),
            'author_id': qnr['author']['reference'].split('/')[-1],
            'site_name': get_site(qnr),
            # Todo: correctly pick external study of interest
            'study_id': get_identifier(
                qnr['subject']['identifier'],
                system=TRUENTH_EXTERNAL_STUDY_SYSTEM
            ),
            'authored': qnr['authored'],
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
                            # Todo: lookup option text from stored Questionnaire
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


def parse_concepts(elements, system):
    """recursive function to build array of concepts from nested structure"""
    ccs = []
    for element in elements:
        ccs.append(Coding(code=element['code'],
                          display=element['display'],
                          system=system))
        if 'concept' in element:
            ccs += parse_concepts(element['concept'], system)
    return ccs


def fetch_HL7_V3_Namespace(valueSet):
    """Pull and parse the published FHIR ethnicity namespace"""
    src_url = 'http://hl7.org/fhir/v3/{valueSet}/v3-{valueSet}.cs.json'.format(
        valueSet=valueSet)
    response = requests.get(src_url)
    load = response.text
    return parse_concepts(response.json()['concept'],
                          system='http://hl7.org/fhir/v3/{}'.format(valueSet))


def fetch_local_valueset(valueSet):
    """Pull and parse the named valueSet from our local definition"""
    response = valueset_nhhd_291036()
    return parse_concepts(response.json['codeSystem']['concept'],
                          system='{}/{}'.format(TRUENTH_VALUESET, valueSet))


def add_static_concepts(only_quick=False):
    """Seed database with default static concepts

    Idempotent - run anytime to push any new concepts into existing dbs

    :param only_quick: For unit tests needing quick loads, set true
        unless the test needs the slow to load race and ethnicity data.

    """
    from .procedure_codes import TxStartedConstants, TxNotStartedConstants

    concepts = fetch_local_valueset(NHHD_291036)
    if not only_quick:
        concepts += fetch_HL7_V3_Namespace('Ethnicity')
        concepts += fetch_HL7_V3_Namespace('Race')
    for concept in concepts:
        if not Coding.query.filter_by(code=concept.code,
                                      system=concept.system).first():
            db.session.add(concept)

    for clinical_concepts in CC:
        if not clinical_concepts in db.session():
            db.session.add(clinical_concepts)

    for encounter_type in EC:
        if not encounter_type in db.session():
            db.session.add(encounter_type)

    for concept in LocaleConstants():
        pass  # looping is adequate
    for concept in TxStartedConstants():
        pass  # looping is adequate
    for concept in TxNotStartedConstants():
        pass  # looping is adequate


def v_or_n(value):
    """Return None unless the value contains data"""
    return value.rstrip() if value else None


def v_or_first(value, field_name):
    """Return desired from list or scalar value

    :param value: the raw data, may be a single value (directly
     returned) or a list from which the first element will be returned
    :param field_name: used in error text when multiple values
     are found for a constrained item.

    Some fields, such as `name` were assumed to always be a single
    dictionary containing single values, whereas the FHIR spec
    defines them to support 0..* meaning we must handle a list.

    NB - as the datamodel still only expects one, a 400 will be
    raised if given multiple values, using the `field_name` in the text.

    """
    if isinstance(value, (tuple, list)):
        if len(value) > 1:
            msg = "Can't handle multiple values for `{}`".format(field_name)
            current_app.logger.warn(msg)
            abort(400, msg)
        return value[0]
    return value
