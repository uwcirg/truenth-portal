"""Model classes for retaining FHIR data"""
from datetime import date, datetime
import json
from sqlalchemy.dialects.postgresql import JSONB, ENUM
import urllib

from ..extensions import db

def as_fhir(obj):
    """For builtin types needing FHIR formatting help

    Returns obj as JSON FHIR formatted string

    """
    if hasattr(obj, 'as_fhir'):
        return obj.as_fhir()
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%dT%H:%M:%S%z")
    if isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')


class CodeableConcept(db.Model):
    __tablename__ = 'codeable_concepts'
    id = db.Column(db.Integer, primary_key=True)
    system = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(80), nullable=False)
    display = db.Column(db.Text, nullable=False)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "CodeableConcept {0.code}, {0.display}, {0.system}".format(self)

    @classmethod
    def from_fhir(cls, data):
        """Factory method to lookup or create instance from fhir"""
        cc = cls()
        coding = data['coding'][0]
        for i in ("system", "code", "display"):
            if i in coding:
                cc.__setattr__(i, coding[i])
        return cc.add_if_not_found()

    def as_fhir(self):
        """Return self in JSON FHIR formatted string"""
        d = {}
        for i in ("system", "code", "display"):
            if getattr(self, i):
                d[i] = getattr(self, i)
        return {"coding": [d,]}

    def add_if_not_found(self):
        """Add self to database, or return existing

        Queries for similar, existing CodeableConcept (matches on
        system and code alone).  Populates self.id if found, adds
        to database first if not.

        """
        self = db.session.merge(self)
        if self.id:
            return self

        match = self.query.filter_by(system=self.system,
                code=self.code).first()
        if not match:
            db.session.add(self)
        elif self is not match:
            self = db.session.merge(match)
        return self


""" TrueNTH Clinical Codes """
TRUENTH_CODE_SYSTEM = 'http://us.truenth.org/clinical-codes'
BIOPSY = CodeableConcept(system=TRUENTH_CODE_SYSTEM, code='111',
                         display='biopsy')
PCaDIAG = CodeableConcept(system=TRUENTH_CODE_SYSTEM, code='121',
                          display='PCa diagnosis')
TX = CodeableConcept(system=TRUENTH_CODE_SYSTEM, code='131',
                          display='treatment begun')


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
                               self.value, self.units, self.system,
                               self.code if x is not None])
        return "ValueQuantity " + components

    def as_fhir(self):
        """Return self in JSON FHIR formatted string"""
        d = {}
        for i in ("value", "units", "system", "code"):
            if getattr(self, i):
                d[i] = getattr(self, i)
        return {"valueQuantity": d}

    def add_if_not_found(self):
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
        elif self is not match:
            self = db.session.merge(match)
        return self


class Observation(db.Model):
    __tablename__ = 'observations'
    id = db.Column(db.Integer, primary_key=True)
    issued = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(80))
    codeable_concept_id = db.Column(db.ForeignKey('codeable_concepts.id'))
    value_quantity_id = db.Column(db.ForeignKey('value_quantities.id'))

    codeable_concept = db.relationship(CodeableConcept, cascade="save-update")
    value_quantity = db.relationship(ValueQuantity)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "Observation {0.codeable_concept} {0.value_quantity} "\
                "at {0.issued} with status {0.status} ".format(self)

    def as_fhir(self):
        """Return self in JSON FHIR formatted string"""
        fhir = {"resourceType": "Observation"}
        if self.issued:
            fhir['issued'] = as_fhir(self.issued)
        if self.status:
            fhir['status'] = self.status
        fhir['code'] = self.codeable_concept.as_fhir()
        fhir.update(self.value_quantity.as_fhir())
        return fhir

    def add_if_not_found(self):
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
        elif self is not match:
            self = db.session.merge(match)
        return self


class UserObservation(db.Model):
    __tablename__ = 'user_observations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'))
    observation_id = db.Column(db.ForeignKey('observations.id'))

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


class UserEthnicity(db.Model):
    __tablename__ = 'user_ethnicities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id', ondelete='CASCADE'))
    codeable_concept_id = db.Column(db.ForeignKey('codeable_concepts.id'))

    codeable_concept = db.relationship(CodeableConcept, cascade="save-update")

    def add_if_not_found(self):
        """Add self to database, or return existing

        Queries for matching, existing UserEthnicity.
        Populates self.id if found, adds to database first if not.

        """
        if self.id:
            return self

        match = self.query.filter_by(user_id=self.user_id,
                codeable_concept_id=self.codeable_concept_id).first()
        if not match:
            db.session.add(self)
        elif self is not match:
            self = db.session.merge(match)
        return self



class UserRace(db.Model):
    __tablename__ = 'user_races'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id', ondelete='CASCADE'))
    codeable_concept_id = db.Column(db.ForeignKey('codeable_concepts.id'))

    codeable_concept = db.relationship(CodeableConcept, cascade="save-update")

    def add_if_not_found(self):
        """Add self to database, or return existing

        Queries for matching, existing UserRace.
        Populates self.id if found, adds to database first if not.

        """
        if self.id:
            return self

        match = self.query.filter_by(user_id=self.user_id,
                codeable_concept_id=self.codeable_concept_id).first()
        if not match:
            db.session.add(self)
        elif self is not match:
            self = db.session.merge(match)
        return self


class QuestionnaireResponse(db.Model):

    def default_status(context):
        return context.current_parameters['document']['status']

    def default_authored(context):
        return context.current_parameters['document']['authored']

    __tablename__ = 'questionnaire_responses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'))
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
        return "QuestionnaireResponse {0.id} for user {0.user_id} "\
                "{0.status} {0.authored}".format(self)


def parse_concepts(elements, system):
    "recursive function to build array of concepts from nested structure"
    ccs = []
    for element in elements:
        ccs.append(CodeableConcept(code=element['code'],
                                   display=element['display'],
                                   system=system))
        if 'concept' in element:
            ccs += parse_concepts(element['concept'], system)
    return ccs


def fetch_HL7_V3_Namespace(valueSet):
    """Pull and parse the published FHIR ethnicity namespace"""
    src_url = 'http://hl7.org/fhir/v3/{valueSet}/v3-{valueSet}.json'.format(
        valueSet=valueSet)
    response = urllib.urlopen(src_url)
    data = json.loads(response.read())
    return parse_concepts(data['codeSystem']['concept'],
                          system='http://hl7.org/fhir/v3/{}'.format(valueSet))


def add_static_concepts():
    """Seed database with default static concepts

    Idempotent - run anytime to push any new concepts into existing dbs

    """
    concepts = fetch_HL7_V3_Namespace('Ethnicity')
    for concept in concepts:
        if not CodeableConcept.query.filter_by(code=concept.code,
                                               system=concept.system).first():
            db.session.add(concept)

    concepts = fetch_HL7_V3_Namespace('Race')
    for concept in concepts:
        if not CodeableConcept.query.filter_by(code=concept.code,
                                               system=concept.system).first():
            db.session.add(concept)
