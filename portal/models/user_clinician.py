"""Model for UserClinician"""
from ..database import db


class UserClinician(db.Model):
    """Link table between patient and clinicians, both users"""
    __tablename__ = 'user_clinicians'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    clinician_id = db.Column(db.ForeignKey('users.id'), nullable=False)
