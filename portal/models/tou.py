"""ToU (Terms of Use)  module"""
from ..database import db


class ToU(db.Model):
    """SQLAlchemy class for `tou` table"""
    __tablename__ = 'tou'
    id = db.Column(db.Integer(), primary_key=True)
    agreement_url = db.Column(db.Text,
                              server_default='predates agreement_url',
                              nullable=False)
    audit_id = db.Column(db.ForeignKey('audit.id'), nullable=False)

    audit = db.relationship('Audit', cascade="save-update", lazy='joined')
    """tracks when and by whom the terms were agreed to"""

    def __str__(self):
        return "ToU ({0.audit}) {0.agreement_url}".format(self)
