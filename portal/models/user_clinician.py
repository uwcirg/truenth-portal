"""Model for UserClinician"""
from ..database import db


class UserClinician(db.Model):
    """Basic link table for clinicians with optional PI flag

    Link any patient with a clinician - both FKs to the users table.
    """
    __tablename__ = 'user_clinicians'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    clinician_id = db.Column(db.ForeignKey('users.id'), nullable=False)
