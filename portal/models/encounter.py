"""Model classes for patient encounters.

Designed around FHIR guidelines for representation of encounters.
"""
from datetime import datetime

from sqlalchemy import Enum

from ..database import db
from ..date_tools import FHIR_datetime, as_fhir
from ..system_uri import TRUENTH_ENCOUNTER_CODE_SYSTEM
from .codeable_concept import CodeableConcept
from .coding import Coding
from .lazy import lazyprop
from .reference import Reference
from .role import ROLE


class EncounterCodings(db.Model):
    """Link table joining Encounter with n Encounter types"""

    __tablename__ = 'encounter_codings'
    id = db.Column(db.Integer, primary_key=True)
    encounter_id = db.Column(db.ForeignKey('encounters.id'), index=True, nullable=False)
    coding_id = db.Column(db.ForeignKey('codings.id'), nullable=False)


# http://www.hl7.org/FHIR/encounter-definitions.html#Encounter.status
status_types = Enum(
    'planned', 'arrived', 'in-progress', 'onleave', 'finished', 'cancelled',
    name='statuses', create_type=False)

# authentication method type extension to the standard FHIR format
auth_method_types = Enum(
    'password_authenticated', 'url_authenticated', 'staff_authenticated',
    'staff_handed_to_patient', 'service_token_authenticated',
    'url_authenticated_and_verified', 'failsafe',
    name='auth_methods', create_type=False)


class Encounter(db.Model):
    """Model representing a FHIR encounter

    Per FHIR guidelines, encounters are defined as interactions between
    a patient and healthcare provider(s) for the purpose of providing
    healthcare service(s) or assessing the health status of a patient.

    """
    __tablename__ = 'encounters'
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column('status', status_types, index=True, nullable=False)
    user_id = db.Column(
        db.ForeignKey(
            'users.id',
            name='encounters_user_id_fk'),
        index=True,
        nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    """required whereas end_time is optional
    """
    end_time = db.Column(db.DateTime, nullable=True)
    """when not defined, Period is assumed to be ongoing
    """
    auth_method = db.Column('auth_method', auth_method_types, nullable=False)
    type = db.relationship("Coding", secondary='encounter_codings')

    def __str__(self):
        """Log friendly string format"""

        def period():
            if self.end_time:
                return "{} to {}".format(
                    FHIR_datetime.as_fhir(self.start_time),
                    FHIR_datetime.as_fhir(self.end_time))
            return FHIR_datetime.as_fhir(self.start_time)

        return "Encounter of status {} on {} via {} from {}".format(
            self.status, self.user_id, self.auth_method, period())

    def as_fhir(self):
        """produces FHIR representation of encounter in JSON format"""
        d = {}
        d['resourceType'] = 'Encounter'
        d['id'] = self.id
        d['status'] = self.status
        d['patient'] = Reference.patient(self.user_id).as_fhir()
        d['period'] = {'start': as_fhir(self.start_time)}
        if self.end_time:
            d['period']['end'] = as_fhir(self.end_time)
        if self.type:
            d['type'] = [coding.as_fhir() for coding in self.type]
        d['auth_method'] = self.auth_method
        return d

    @classmethod
    def from_fhir(cls, data):
        """Parses FHIR data to produce a new encounter instance"""
        p = cls()
        p.status = data['status']
        p.user_id = Reference.parse(data['patient']).id
        period = data['period']
        p.start_time = FHIR_datetime.parse(
            period['start'], error_subject='period.start')
        if 'end' in period:
            p.end_time = FHIR_datetime.parse(
                period['end'], error_subject='period.end')
        p.auth_method = data['auth_method']
        return p


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

    @lazyprop
    def INTERVIEW_ASSISTED(self):
        coding = Coding(
            system=TRUENTH_ENCOUNTER_CODE_SYSTEM,
            code='interview_assisted',
            display='Information collected in-person',
        ).add_if_not_found(True)
        cc = CodeableConcept(codings=[coding, ]).add_if_not_found(True)
        assert coding in cc.codings
        return cc


EC = EncounterConstants()


def initiate_encounter(user, auth_method):
    """On login, generate a new encounter for given user and auth_method

    We use encounters to track authentication mechanisms.  Given the
    unreliable nature of logout (server may have cycled, may miss a
    timeout, etc.) take this opportunity to clean up any existing
    encounters that are still open.

    """
    # Look for any stale encounters needing to be closed out.
    finish_encounter(user)

    # Service users appear to have provided password, but get their
    # own special label
    if user.has_role(ROLE.SERVICE.value):
        auth_method = 'service_token_authenticated'

    # If the auth_method is unknown, fall back to failsafe
    if auth_method is None:
        auth_method = 'failsafe'

    # Initiate new as directed
    encounter = Encounter(
        status='in-progress', auth_method=auth_method,
        start_time=datetime.utcnow(), user_id=user.id)
    db.session.add(encounter)
    db.session.commit()
    return db.session.merge(encounter)


def finish_encounter(user):
    """On logout, terminate user's active encounter, if found """
    assert (user)
    now = datetime.utcnow()
    # Look for any stale encounters needing to be closed out.
    query = Encounter.query.filter(Encounter.user_id == user.id).filter(
        Encounter.status == 'in-progress').filter(Encounter.end_time.is_(None))
    for encounter in query:
        encounter.status = 'finished'
        encounter.end_time = now
