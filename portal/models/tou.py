"""ToU (Terms of Use)  module"""
from sqlalchemy.dialects.postgresql import ENUM

from ..database import db
from ..date_tools import FHIR_datetime

tou_types = ENUM('website terms of use', 'subject website consent',
                 'stored website consent form', 'privacy policy',
                 name='tou_types', create_type=False)


class ToU(db.Model):
    """SQLAlchemy class for `tou` table"""
    __tablename__ = 'tou'
    id = db.Column(db.Integer(), primary_key=True)
    agreement_url = db.Column(db.Text,
                              server_default='predates agreement_url',
                              nullable=False)
    audit_id = db.Column(db.ForeignKey('audit.id'), nullable=False)
    organization_id = db.Column(db.ForeignKey('organizations.id'))
    type = db.Column('type', tou_types, nullable=False)

    audit = db.relationship('Audit', cascade="save-update", lazy='joined')
    """tracks when and by whom the terms were agreed to"""

    def __str__(self):
        return "ToU ({0.audit}) {0.agreement_url}".format(self)

    def as_json(self):
        d = {}
        d['id'] = self.id
        d['agreement_url'] = self.agreement_url
        d['accepted'] = FHIR_datetime.as_fhir(self.audit.timestamp)
        d['type'] = self.type

        return d
