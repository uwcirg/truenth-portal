"""Module for PatientList, used specifically to populate and page patients"""
from ..database import db

"""Maintain columns for all list fields, all indexed for quick sort

- TrueNTH ID
- Username  # omitting, duplicate of email
- First Name
- Last Name
- Date of Birth
- Email
- Questionnaire Status
- Visit
- Study ID
- Study Consent Date (GMT)
- Sites(s)
- Interventions  # omitting, obsolete

"""
class PatientList(db.Model):
    # PLEASE maintain merge_with() as user model changes #
    __tablename__ = 'patient_list'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64), index=True)
    last_name = db.Column(db.String(64), index=True)
    birthdate = db.Column(db.Date, index=True)
    email = db.Column(db.String(120), index=True)
    questionnaire_status = db.Column(db.Text, index=True)
    visit = db.Column(db.Text, index=True)
    study_id = db.Column(db.Text, index=True)
    consent_date = db.Column(db.DateTime, index=True)
    sites = db.Column(db.Text, index=True)
    deleted = db.Column(db.Boolean, default=False)
    test_role = db.Column(db.Boolean)
    org_id = db.Column(db.ForeignKey('organizations.id'))  # used for access control


def patient_list_update_patient(patient_id):
    """Update given patient"""
    from .user import User
    from .role import ROLE
    patient = PatientList.query.get(patient_id)
    if not patient:
        patient = PatientList(id=patient_id)
        db.session.add(patient)

    user = User.query.get(patient_id)
    patient.first_name = user.first_name
    patient.last_name = user.last_name
    patient.email = user.email
    patient.birthdate = user.birthdate
    patient.deleted = user.deleted_id is not None
    patient.test_role = True if user.has_role(ROLE.TEST.value) else False
    patient.org_id = user.organizations[0].id if user.organizations else None

    # TODO
    # qb_status = qb_status_visit_name(
    #     patient.id, research_study_id, cached_as_of_key)
    # patient.assessment_status = _(qb_status['status'])
    # patient.current_qb = qb_status['visit_name']
    # if research_study_id == EMPRO_RS_ID:
    #     patient.clinician = '; '.join(
    #         (clinician_name_map.get(c.id, "not in map") for c in
    #          patient.clinicians)) or ""
    #     patient.action_state = qb_status['action_state'].title() \
    #         if qb_status['action_state'] else ""
    db.session.commit()
