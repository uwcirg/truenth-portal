from ..database import db
from .coding import Coding


class CodeableConceptCoding(db.Model):
    """Link table joining CodeableConcept with n Codings"""

    __tablename__ = 'codeable_concept_codings'
    id = db.Column(db.Integer, primary_key=True)
    codeable_concept_id = db.Column(db.ForeignKey(
        'codeable_concepts.id'), nullable=False)
    coding_id = db.Column(db.ForeignKey('codings.id'), nullable=False)

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
        text = "{} ".format(self.text) if self.text else ''
        summary = "CodeableConcept {}[".format(text)
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
