"""Module for PatientList, used specifically to populate and page patients"""
from datetime import datetime, timedelta
from ..database import db
from .research_study import BASE_RS_ID, EMPRO_RS_ID


class PatientList(db.Model):
    """Maintain columns for all list fields, all indexed for quick sort

    Table used to generate pages of results for patient lists.  Acts
    as a cache, values should be updated on any change (questionnaire,
    demographics, deletion, etc.)

    All columns in both patients and sub-study lists are defined.
    """
    __tablename__ = 'patient_list'
    userid = db.Column(db.Integer, primary_key=True)
    study_id = db.Column(db.Text, index=True)
    firstname = db.Column(db.String(64), index=True)
    lastname = db.Column(db.String(64), index=True)
    birthdate = db.Column(db.Date, index=True)
    email = db.Column(db.String(120), index=True)
    questionnaire_status = db.Column(db.Text, index=True)
    empro_status = db.Column(db.Text, index=True)
    clinician = db.Column(db.Text, index=True)
    action_state = db.Column(db.Text, index=True)
    visit = db.Column(db.Text, index=True)
    empro_visit = db.Column(db.Text, index=True)
    consentdate = db.Column(db.DateTime, index=True)
    empro_consentdate = db.Column(db.DateTime, index=True)
    org_name = db.Column(db.Text, index=True)
    deleted = db.Column(db.Boolean, default=False)
    test_role = db.Column(db.Boolean)
    org_id = db.Column(db.ForeignKey('organizations.id'))  # used for access control
    last_updated = db.Column(db.DateTime)


def patient_list_update_patient(patient_id, research_study_id=None):
    """Update given patient

    :param research_study_id: define to optimize time for updating
     only values from the given research_study_id.  by default, all columns
     are (re)set to current info.
    """
    from .qb_timeline import qb_status_visit_name
    from .role import ROLE
    from .user import User
    from .user_consent import consent_withdrawal_dates
    from ..views.clinician import clinician_name_map

    user = User.query.get(patient_id)
    if not user.has_role(ROLE.PATIENT.value):
        return

    patient = PatientList.query.get(patient_id)
    new_record = False
    if not patient:
        new_record = True
        patient = PatientList(userid=patient_id)
        db.session.add(patient)

    # necessary to avoid recursive loop via some update paths
    now = datetime.utcnow()
    if patient.last_updated and patient.last_updated + timedelta(seconds=30) > now:
        return
    patient.last_updated = now

    if research_study_id is None or new_record:
        patient.study_id = user.external_study_id
        patient.firstname = user.first_name
        patient.lastname = user.last_name
        patient.email = user.email
        patient.birthdate = user.birthdate
        patient.deleted = user.deleted_id is not None
        patient.test_role = True if user.has_role(ROLE.TEST.value) else False
        patient.org_id = user.organizations[0].id if user.organizations else None
        patient.org_name = user.organizations[0].name if user.organizations else None

    if research_study_id == BASE_RS_ID or research_study_id is None:
        rs_id = BASE_RS_ID
        qb_status = qb_status_visit_name(
             patient.userid, research_study_id=rs_id, as_of_date=now)
        patient.questionnaire_status = str(qb_status['status'])
        patient.visit = qb_status['visit_name']
        patient.consentdate, _ = consent_withdrawal_dates(user=user, research_study_id=rs_id)

    if (research_study_id == EMPRO_RS_ID or research_study_id is None) and user.clinicians:
        rs_id = EMPRO_RS_ID
        patient.clinician = '; '.join(
            (clinician_name_map().get(c.id, "not in map") for c in
            user.clinicians)) or ""
        qb_status = qb_status_visit_name(
            patient.userid, research_study_id=rs_id, as_of_date=now)
        patient.empro_status = str(qb_status['status'])
        patient.empro_visit = qb_status['visit_name']
        patient.action_state = qb_status['action_state'].title() \
            if qb_status['action_state'] else ""
        patient.empro_consentdate, _ = consent_withdrawal_dates(
            user=user, research_study_id=rs_id)
    db.session.commit()
