"""Model classes for retaining FHIR data"""
from collections import OrderedDict
from datetime import date, datetime, timedelta
from dateutil import parser
from flask import abort, current_app
import json
import pytz
from sqlalchemy import UniqueConstraint, or_
from sqlalchemy.dialects.postgresql import JSONB, ENUM
import requests

from ..extensions import db
from .lazy import lazyprop
from ..system_uri import TRUENTH_CLINICAL_CODE_SYSTEM, TRUENTH_VALUESET
from ..system_uri import NHHD_291036
from ..views.fhir import valueset_nhhd_291036


def as_fhir(obj):
    """For builtin types needing FHIR formatting help

    Returns obj as JSON FHIR formatted string

    """
    if hasattr(obj, 'as_fhir'):
        return obj.as_fhir()
    if isinstance(obj, datetime):
        # Make SURE we only communicate unaware or UTC timezones
        tz = getattr(obj, 'tzinfo', None)
        if tz and tz != pytz.utc:
            current_app.logger.error("Datetime export of NON-UTC timezone")
        return obj.strftime("%Y-%m-%dT%H:%M:%S%z")
    if isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')


class FHIR_datetime(object):
    """Utility class/namespace for working with FHIR datetimes"""

    @staticmethod
    def as_fhir(obj):
        return as_fhir(obj)

    @staticmethod
    def parse(data, error_subject=None):
        """Parse input string to generate a UTC datetime instance

        NB - date must be more recent than year 1900 or a ValueError
        will be raised.

        :param data: the datetime string to parse
        :param error_subject: Subject string to use in error message

        :return: UTC datetime instance from given data

        """
        # As we use datetime.strftime for display, and it can't handle dates
        # older than 1900, treat all such dates as an error
        epoch = datetime.strptime('1900-01-01', '%Y-%m-%d')
        try:
            dt = parser.parse(data)
        except ValueError:
            msg = "Unable to parse {}: {}".format(error_subject, data)
            current_app.logger.warn(msg)
            abort(400, msg)
        if dt.tzinfo:
            epoch = pytz.utc.localize(epoch)
            # Convert to UTC if necessary
            if dt.tzinfo != pytz.utc:
                dt = dt.astimezone(pytz.utc)
        # As we use datetime.strftime for display, and it can't handle dates
        # older than 1900, treat all such dates as an error
        if dt < epoch:
            raise ValueError("Dates prior to year 1900 not supported")
        return dt

    @staticmethod
    def now():
        """Generates a FHIR compliant datetime string for current moment"""
        return datetime.utcnow().isoformat()+'Z'


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
        fhir['code'] = self.codeable_concept.as_fhir()
        fhir.update(self.value_quantity.as_fhir())
        if self.performers:
            fhir['performer'] = [p.as_fhir() for p in self.performers]
        return fhir

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

def aggregate_responses(instrument_ids):
    """Build a bundle of QuestionnaireResponses

    :param instrument_ids: list of instrument_ids to restrict results to

    """
    annotated_questionnaire_responses = []
    questionnaire_responses = QuestionnaireResponse.query.order_by(QuestionnaireResponse.authored.desc())

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
        questionnaire_response.document["subject"] = {
            k:v for k,v in subject.as_fhir().items() if k in patient_fields
        }

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
    """Function for generating a CSV from a bundle of QuestionnaireResponses"""
    def get_identifier(id_list, **kwargs):
        """Return first identifier object matching kwargs"""
        for identifier in id_list:
            for k,v in kwargs.items():
                if identifier.get(k) != v:
                    break
            else:
                return identifier['value']
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

    columns = (
        'identifier',
        'study_id',
        'subject_id',
        'author_id',
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
            'subject_id': get_identifier(
                qnr['subject']['identifier'],
                use='official'
            ),
            'author_id': qnr['author']['reference'].split('/')[-1],
            # Todo: correctly pick external study of interest
            'study_id': get_identifier(
                qnr['subject']['identifier'],
                system='http://us.truenth.org/identity-codes/external-study-id'
            ),
            'authored': qnr['authored'],
            'instrument': qnr['questionnaire']['reference'].split('/')[-1],
        }
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
    src_url = 'http://hl7.org/fhir/v3/{valueSet}/v3-{valueSet}.json'.format(
        valueSet=valueSet)
    response = requests.get(src_url)
    load = response.text
    data = json.loads(load)
    return parse_concepts(data['codeSystem']['concept'],
                          system='http://hl7.org/fhir/v3/{}'.format(valueSet))

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

    for concept in TxStartedConstants(): pass  # looping is adequate
    for concept in TxNotStartedConstants(): pass  # looping is adequate


def localized_PCa(user):
    """Look up user's value for localized PCa"""
    from .organization import Organization, OrgTree

    # Some systems use organization affiliation to note
    # if a user has what we call a 'localized diagnosis'
    if current_app.config.get('LOCALIZED_AFFILIATE_ORG', None):
        localized_org = Organization.query.filter_by(
            name=current_app.config.get('LOCALIZED_AFFILIATE_ORG')).one()
        ot = OrgTree()
        consented_orgs = [c.organization_id for c in user.valid_consents]
        if ot.at_or_below_ids(localized_org.id, consented_orgs):
            return True
        return False
    else:
        codeable_concept = CC.PCaLocalized
        value_quantities = user.fetch_values_for_concept(codeable_concept)
        if value_quantities:
            assert len(value_quantities) == 1
            return value_quantities[0].value == 'true'
        return False


def most_recent_survey(user, instrument_id=None):
    """Look up timestamp for recent QuestionnaireResponse for user

    :param user: Patient to whom completed QuestionnaireResponses belong
    :param instrument_id: Optional parameter to limit type of
        QuestionnaireResponse in lookup.
    :return: dictionary with authored (timestamp) of the most recent
        QuestionnaireResponse keyed by status found

    """
    query = QuestionnaireResponse.query.distinct(
        QuestionnaireResponse.status).filter(
        QuestionnaireResponse.subject_id == user.id)
    if instrument_id:
        query = query.filter(
            QuestionnaireResponse.document[
                ("questionnaire", "reference")
            ].astext.endswith(instrument_id))

    query = query.order_by(
        QuestionnaireResponse.status,
        QuestionnaireResponse.authored).limit(
            5).with_entities(QuestionnaireResponse.status,
                            QuestionnaireResponse.authored)
    results = {}
    for qr in query:
        if qr[1] not in results:
            results[qr[0]] = qr[1]
    return results



class AssessmentStatus(object):
    """Lookup and hold assessment status detail for a user

    Complicated task due to nature of multiple instruments which differ
    depending on user state such as localized or metastatic.

    """

    def __init__(self, user, consent=None):
        """Initialize assessment status object for given user/consent

        :param user: The user in question - patient on whom to check status
        :param consent: Consent agreement defining dates and which organization
            to consider in the status check.  If not provided, use the first
            valid consent found for the user.  Users w/o consents have
            overall_status of `Expired`

        """
        self.user = user
        self._consent = consent
        self._overall_status, self._consent_date = None, None
        self._localized = localized_PCa(user)
        self.instrument_status = OrderedDict()

    @property
    def consent_date(self):
        """Return timestamp of signed consent, if available, else None"""

        if self._consent_date:
            return self._consent_date

        # If we aren't given a consent, use the first valid consent found
        # for the user.
        if not self._consent:
            if self.user.valid_consents and len(list(self.user.valid_consents)) > 0:
                self._consent = self.user.valid_consents[0]

        if self._consent:
            self._consent_date = self._consent.audit.timestamp
        else:
            # Tempting to call this invalid state, but it's possible
            # the consent has been revoked, treat as expired.
            self._consent_date = None
        return self._consent_date

    @property
    def completed_date(self):
        """Returns timestamp from completed assessment, if available"""
        self.__obtain_status_details()
        best_date = None
        for instrument, details in self.instrument_status.items():
            if 'completed' in details:
                # TODO: in event of multiple completed instruments,
                # not sure *which* date is best??
                best_date = details['completed']
        return best_date

    @property
    def localized(self):
        return self._localized

    @property
    def overall_status(self):
        """Returns display quality string for user's overall status"""
        self.__obtain_status_details()
        return self._overall_status

    def instruments_needing_full_assessment(self):
        self.__obtain_status_details()
        results = []
        for instrument_id, details in self.instrument_status.items():
            if 'completed' in details or 'in-progress' in details:
                continue
            results.append(instrument_id)
        return results

    def instruments_in_process(self):
        self.__obtain_status_details()
        results = []
        for instrument_id, details in self.instrument_status.items():
            if 'in-progress' in details:
                results.append(instrument_id)
        return results

    def __obtain_status_details(self):
        # expensive process - do once
        if hasattr(self, '_details_obtained'):
            return
        if not self.consent_date:
            self._overall_status = 'Expired'
            self._details_obtained = True
            return
        if self.localized:
            thresholds = (
                (7, "Due"),
                (90, "Overdue"),
            )
            for instrument in ('epic26', 'eproms_add'):
                self.__status_per_instrument(instrument, thresholds)
        else:
            # assuming metastaic - although it's possible the user just didn't
            # answer the localized question
            thresholds = (
                (1, "Due"),
                (30, "Overdue")
            )
            for instrument in ('eortc', 'hpfs', 'prems', 'irondemog'):
                self.__status_per_instrument(instrument, thresholds)

        status_strings = [details['status'] for details in
                          self.instrument_status.values()]

        if all(status_strings[0] == status for status in status_strings):
            # All intruments in the same state - use the common value
            self._overall_status = status_strings[0]
        else:
            if any("Expired" == status for status in status_strings):
                # At least one expired, but not all
                self._overall_status = "Partially Completed"
            self._overall_status = "In Progress"
        self._details_obtained = True

    def __status_per_instrument(self, instrument_id, thresholds):
        """Returns status for one instrument

        :param instrument_id: the instument in question
        :param thresholds: series of day counts and status strings.
            NB - these must be ordered with increasing values.

        :return: matching status string from constraints

        """
        def status_from_recents(recents):
            if 'completed' in recents:
                return "Completed"
            if 'in-progress' in recents:
                return "In Progress"
            today = datetime.utcnow()
            delta = today - self.consent_date
            for days_allowed, message in thresholds:
                if delta < timedelta(days=days_allowed+1):
                    return message
            return "Expired"

        if not instrument_id in self.instrument_status:
            self.instrument_status[instrument_id] = most_recent_survey(
                self.user, instrument_id)
        if not 'status' in self.instrument_status[instrument_id]:
            self.instrument_status[instrument_id]['status'] =\
                    status_from_recents(self.instrument_status[instrument_id])
