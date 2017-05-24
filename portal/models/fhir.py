"""Model classes for retaining FHIR data"""
from datetime import datetime
import json
from sqlalchemy import UniqueConstraint, or_
from sqlalchemy.dialects.postgresql import JSONB, ENUM
import requests

from ..database import db
from ..date_tools import as_fhir, FHIR_datetime
from .lazy import lazyprop
from .organization import OrgTree
from .reference import Reference
from ..system_uri import TRUENTH_CLINICAL_CODE_SYSTEM, TRUENTH_ENCOUNTER_CODE_SYSTEM, TRUENTH_VALUESET
from ..system_uri import NHHD_291036
from ..views.fhir import valueset_nhhd_291036


class CodeableConceptCoding(db.Model):
    """Link table joining CodeableConcept with n Codings"""

    __tablename__ = 'codeable_concept_codings'
    id = db.Column(db.Integer, primary_key=True)
    codeable_concept_id = db.Column(db.ForeignKey(
        'codeable_concepts.id'), nullable=False)
    coding_id =  db.Column(db.ForeignKey('codings.id'), nullable=False)

    # Maintain a unique relationship between each codeable concept
    # and it list of codings.  Therefore, a CodeableConcept always
    # contains the superset of all codings given for the concept.
    db.UniqueConstraint('codeable_concept_id', 'coding_id',
                        name='unique_codeable_concept_coding')


class CodeableConcept(db.Model):
    __tablename__ = 'codeable_concepts'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text)
    codings = db.relationship("Coding", secondary='codeable_concept_codings')

    def __str__(self):
        """Print friendly format for logging, etc."""
        summary = "CodeableConcept {} [".format(
            self.text if self.text else '')
        summary += ','.join([str(coding) for coding in self.codings])
        return summary + ']'

    @classmethod
    def from_fhir(cls, data):
        cc = cls()
        if 'text' in data:
            cc.text = data['text']
        for coding in data['coding']:
            item = Coding.from_fhir(coding)
            cc.codings.append(item)
        return cc.add_if_not_found()

    def as_fhir(self):
        """Return self in JSON FHIR formatted string"""
        d = {"coding": [coding.as_fhir() for coding in self.codings]}
        if self.text:
            d['text'] = self.text
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, matching on the set of contained
        codings alone.  Adds if no match is found.

        @return: the new or matched CodeableConcept

        """
        # we're imposing a constraint, where any CodeableConcept pointing
        # at a particular Coding will be the ONLY CodeableConcept for that
        # particular Coding.
        coding_ids = [c.id for c in self.codings if c.id]
        if not coding_ids:
            raise ValueError("Can't add CodeableConcept without any codings")
        query = CodeableConceptCoding.query.filter(
            CodeableConceptCoding.coding_id.in_(coding_ids)).distinct(
                CodeableConceptCoding.codeable_concept_id)
        if query.count() > 1:
            raise ValueError(
                "DB problem - multiple CodeableConcepts {} found for "
                "codings: {}".format(
                    [cc.codeable_concept_id for cc in query],
                    [str(c) for c in self.codings]))
        if not query.count():
            # First time for this (set) of codes, add new rows
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        else:
            # Build a union of all codings found, old and new
            found = query.first()
            old = CodeableConcept.query.get(found.codeable_concept_id)
            self.text = self.text if self.text else old.text
            self.codings = list(set(old.codings).union(set(self.codings)))
            self.id = found.codeable_concept_id
        self = db.session.merge(self)
        return self


class Coding(db.Model):
    __tablename__ = 'codings'
    id = db.Column(db.Integer, primary_key=True)
    system = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(80), nullable=False)
    display = db.Column(db.Text, nullable=False)
    __table_args__ = (UniqueConstraint('system', 'code',
        name='_system_code'),)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "Coding {0.code}, {0.display}, {0.system}".format(self)

    @classmethod
    def from_fhir(cls, data):
        """Factory method to lookup or create instance from fhir"""
        cc = cls()
        for i in ("system", "code", "display"):
            if i in data:
                cc.__setattr__(i, data[i])
        return cc.add_if_not_found(True)

    def as_fhir(self):
        """Return self in JSON FHIR formatted string"""
        d = {}
        for i in ("system", "code", "display"):
            if getattr(self, i):
                d[i] = getattr(self, i)
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, existing CodeableConcept (matches on
        system and code alone).  Populates self.id if found, adds
        to database first if not.

        """
        if self.id:
            return self

        match = self.query.filter_by(system=self.system,
                code=self.code).first()
        if not match:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        elif self is not match:
            self = db.session.merge(match)
        return self


""" TrueNTH Clinical Codes """
class ClinicalConstants(object):

    def __iter__(self):
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            yield getattr(self, attr)

    @lazyprop
    def BIOPSY(self):
        coding = Coding.query.filter_by(
            system=TRUENTH_CLINICAL_CODE_SYSTEM, code='111').one()
        cc = CodeableConcept(codings=[coding,]).add_if_not_found(True)
        assert coding in cc.codings
        return cc

    @lazyprop
    def PCaDIAG(self):
        coding = Coding.query.filter_by(
            system=TRUENTH_CLINICAL_CODE_SYSTEM, code='121').one()
        cc = CodeableConcept(codings=[coding,]).add_if_not_found(True)
        assert coding in cc.codings
        return cc

    @lazyprop
    def PCaLocalized(self):
        coding = Coding.query.filter_by(
            system=TRUENTH_CLINICAL_CODE_SYSTEM, code='141').one()
        cc = CodeableConcept(codings=[coding,]).add_if_not_found(True)
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
        cc = CodeableConcept(codings=[coding,]).add_if_not_found(True)
        assert coding in cc.codings
        return cc

    @lazyprop
    def PHONE(self):
        coding = Coding(
            system=TRUENTH_ENCOUNTER_CODE_SYSTEM,
            code='phone',
            display='Information collected over telephone system',
        ).add_if_not_found(True)
        cc = CodeableConcept(codings=[coding,]).add_if_not_found(True)
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

    def __str__(self):
        """Print friendly format for logging, etc."""
        components = ','.join([str(x) for x in
                               (self.value, self.units, self.system,
                               self.code) if x is not None])
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
        match = self.query.filter_by(value=lookup_value,
                units=self.units, system=self.system).first()
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
    codeable_concept_id = db.Column(db.ForeignKey('codeable_concepts.id'),
                                   nullable=False)
    value_quantity_id = db.Column(db.ForeignKey('value_quantities.id'),
                                 nullable=False)
    audit_id = db.Column(db.ForeignKey('audit.id'), nullable=False)

    audit = db.relationship('Audit', cascade="save-update")
    codeable_concept = db.relationship(CodeableConcept, cascade="save-update")
    value_quantity = db.relationship(ValueQuantity)
    performers = db.relationship('Performer', lazy='dynamic',
                                 cascade="save-update",
                                 secondary="observation_performers",
                                 backref=db.backref('observations'))

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "Observation {0.codeable_concept} {0.value_quantity} "\
                "at {0.issued} by {0.performers} with status {0.status} ".\
                format(self)

    def as_fhir(self):
        """Return self in JSON FHIR formatted string"""
        fhir = {"resourceType": "Observation"}
        if self.audit:
            fhir['meta'] = self.audit.as_fhir()
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
            issued = FHIR_datetime.parse(data['issued']) if data['issued'] else None
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
                value=v.get('value') or current_v.value,
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
    user_id = db.Column(db.ForeignKey('users.id', ondelete='CASCADE'),
                       nullable=False)
    observation_id = db.Column(db.ForeignKey('observations.id'),
                              nullable=False)
    encounter_id = db.Column(
        db.ForeignKey('encounters.id', name='user_observation_encounter_id_fk'))

    encounter = db.relationship('Encounter')

    __table_args__ = (UniqueConstraint('user_id', 'observation_id',
        name='_user_observation'),)

    def add_if_not_found(self):
        """Add self to database, or return existing

        Queries for matching, existing UserObservation.
        Populates self.id if found, adds to database first if not.

        """
        if self.id:
            return self

        match = self.query.filter_by(user_id=self.user_id,
                observation_id=self.observation_id).first()
        if not match:
            db.session.add(self)
        elif self is not match:
            self = db.session.merge(match)
        return self


class UserIndigenous(db.Model):
    __tablename__ = 'user_indigenous'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id', ondelete='CASCADE'),
                        nullable=False)
    coding_id = db.Column(db.ForeignKey('codings.id'), nullable=False)

    __table_args__ = (UniqueConstraint('user_id', 'coding_id',
        name='_indigenous_user_coding'),)


class UserEthnicity(db.Model):
    __tablename__ = 'user_ethnicities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id', ondelete='CASCADE'),
                        nullable=False)
    coding_id = db.Column(db.ForeignKey('codings.id'), nullable=False)

    __table_args__ = (UniqueConstraint('user_id', 'coding_id',
        name='_ethnicity_user_coding'),)

class UserRace(db.Model):
    __tablename__ = 'user_races'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id', ondelete='CASCADE'),
                        nullable=False)
    coding_id = db.Column(db.ForeignKey('codings.id'), nullable=False)

    __table_args__ = (UniqueConstraint('user_id', 'coding_id',
        name='_race_user_coding'),)

class QuestionnaireResponse(db.Model):

    def default_status(context):
        return context.current_parameters['document']['status']

    def default_authored(context):
        return FHIR_datetime.parse(
            context.current_parameters['document']['authored'])

    __tablename__ = 'questionnaire_responses'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.ForeignKey('users.id'))
    subject = db.relationship("User", back_populates="questionnaire_responses")
    document = db.Column(JSONB)
    encounter_id = db.Column(
        db.ForeignKey('encounters.id', name='qr_encounter_id_fk'))
    encounter = db.relationship("Encounter")

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
        return "QuestionnaireResponse {0.id} for user {0.subject_id} "\
                "{0.status} {0.authored}".format(self)

def aggregate_responses(instrument_ids, current_user):
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
        questionnaire_responses = questionnaire_responses.filter(or_(*instrument_filters))

    patient_fields = ("careProvider", "identifier")

    for questionnaire_response in questionnaire_responses:
        subject = questionnaire_response.subject
        encounter = questionnaire_response.encounter
        encounter_fhir = encounter.as_fhir()
        questionnaire_response.document["encounter"] = encounter_fhir

        questionnaire_response.document["subject"] = {
            k:v for k,v in subject.as_fhir().items() if k in patient_fields
        }

        if subject.organizations:
            questionnaire_response.document["subject"]["careProvider"] = [
                Reference.organization(org.id).as_fhir()
                for org in subject.organizations
            ]

        annotated_questionnaire_responses.append(questionnaire_response.document)

    bundle = {
        'resourceType':'Bundle',
        'updated':FHIR_datetime.now(),
        'total':len(annotated_questionnaire_responses),
        'type': 'searchset',
        'entry':annotated_questionnaire_responses,
    }

    return bundle

def generate_qnr_csv(qnr_bundle):
    """Generate a CSV from a bundle of QuestionnaireResponses"""
    def get_identifier(id_list, **kwargs):
        """Return first identifier object matching kwargs"""
        for identifier in id_list:
            for k,v in kwargs.items():
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
            answer_types.count('valueCoding') != answer_types.count('valueString')
        ):
            return answers

        filtered_answers = []
        for pair in zip(*[iter(answers)]*2):
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
            'paper' in (c.get('code') for c in qnr_data['encounter']['type'])
        ):
            return 'enter manually - paper'
        if row_data.get('subject_id') == row_data.get('author_id'):
            return 'online'
        else:
            return 'enter manually - interview assisted'

    def author_role(row_data, qnr_data):
        if (
            row_data.get('subject_id') == row_data.get('author_id') or
            (
                'type' in qnr_data['encounter'] and
                'paper' in (c.get('code') for c in qnr_data['encounter']['type'])
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
        'subject_id',
        'author_id',
        'author_role',
        'entry_method',
        'authored',
        'instrument',
        'question_code',
        'answer_code',
        'answer',
    )

    yield ','.join('"' + column + '"' for column in columns) + '\n'
    for qnr in qnr_bundle['entry']:
        row_data = {
            'identifier': qnr['identifier']['value'],
            'status': qnr['status'],
            'subject_id': get_identifier(
                qnr['subject']['identifier'],
                use='official'
            ),
            'author_id': qnr['author']['reference'].split('/')[-1],
            'site_name': get_site(qnr),
            # Todo: correctly pick external study of interest
            'study_id': get_identifier(
                qnr['subject']['identifier'],
                system='http://us.truenth.org/identity-codes/external-study-id'
            ),
            'authored': qnr['authored'],
            'instrument': qnr['questionnaire']['reference'].split('/')[-1],
        }
        row_data.update({
            'entry_method': entry_method(row_data, qnr),
            'author_role': author_role(row_data, qnr),
        })
        for question in qnr['group']['question']:
            row_data.update({'question_code': question['linkId']})

            answers = consolidate_answer_pairs(question['answer'])
            for answer in answers:
                # Use first value of answer (most are single-entry dicts)
                answer_data = {'answer': answer.values()[0]}

                # ...unless nested code (ie valueCode)
                if answer.keys()[0] == 'valueCoding':
                    answer_data.update({
                        'answer_code': answer['valueCoding']['code'],

                        # Add suplementary text added earlier
                        # 'answer': answer['valueCoding'].get('text'),
                        'answer': None,
                    })
                row_data.update(answer_data)

                row = []
                for column_name in columns:
                    column = row_data.get(column_name)
                    column = "\N" if column is None else column

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
    data = json.loads(load)
    return parse_concepts(
        data['concept'],
        system='http://hl7.org/fhir/v3/{}'.format(valueSet)
    )

def fetch_local_valueset(valueSet):
    """Pull and parse the named valueSet from our local definition"""
    response = valueset_nhhd_291036()
    data = json.loads(response.data)
    return parse_concepts(data['codeSystem']['concept'],
                          system='{}/{}'.format(TRUENTH_VALUESET,valueSet))


def add_static_concepts(only_quick=False):
    """Seed database with default static concepts

    Idempotent - run anytime to push any new concepts into existing dbs

    :param only_quick: For unit tests needing quick loads, set true
        unless the test needs the slow to load race and ethnicity data.

    """
    from .procedure_codes import TxStartedConstants, TxNotStartedConstants

    BIOPSY = Coding(system=TRUENTH_CLINICAL_CODE_SYSTEM, code='111',
                             display='biopsy')
    PCaDIAG = Coding(system=TRUENTH_CLINICAL_CODE_SYSTEM, code='121',
                              display='PCa diagnosis')
    PCaLocalized = Coding(system=TRUENTH_CLINICAL_CODE_SYSTEM, code='141',
                              display='PCa localized diagnosis')

    # Todo: Shouldn't need to specify these again here...
    concepts = [BIOPSY, PCaDIAG, PCaLocalized]
    concepts += fetch_local_valueset(NHHD_291036)
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

    for concept in TxStartedConstants(): pass  # looping is adequate
    for concept in TxNotStartedConstants(): pass  # looping is adequate
