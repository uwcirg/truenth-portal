"""Model classes for patient encounters.

Designed around FHIR guidelines for representation of encounters.
"""
from ..extensions import db
from .fhir import as_fhir, CodeableConcept, FHIR_datetime
from .reference import Reference


# http://www.hl7.org/FHIR/encounter-definitions.html#Encounter.status
status_types = ENUM('planned', 'arrived', 'in-progress', 'onleave', 'finished',
                    'cancelled', name='statuses', create_type=False)

# authentication method type extension to the standard FHIR format
auth_method_types = ENUM('password_authenticated', 'url_authenticated',
                    'staff_authenticated', 'staff_handed_to_patient',
                    name='auth_methods', create_type=False)

class Encounter(db.Model):
    """Model representing a FHIR encounter

    Per FHIR guidelines, encounters are defined as interactions between
    a patient and healthcare provider(s) for the purpose of providing
    healthcare service(s) or assessing the health status of a patient.

    """
    __tablename__ = 'encounters'
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column('status', status_types)
    user_id = db.Column(db.ForeignKey('users.id'))
    start_time = db.Column(db.DateTime, nullable=False)
    """required whereas end_time is optional
    """
    end_time = db.Column(db.DateTime, nullable=True)
    """when not defined, Period is assumed to be ongoing
    """
    auth_method = db.Column('auth_method', auth_method_types)


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
        d['auth_method'] = self.auth_method
        return d

    @classmethod
    def from_fhir(cls, data, audit):
        """Parses FHIR data to produce a new encounter instance"""
        p = cls(audit=audit)
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
