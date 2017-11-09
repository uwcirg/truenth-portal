"""Research Protocol module"""
from datetime import datetime

from ..database import db
from ..date_tools import FHIR_datetime


class ResearchProtocol(db.Model):
    """ResearchProtocol model for tracking QB versions"""
    __tablename__ = 'research_protocols'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, name):
        self.name = name
        self.created_at = datetime.utcnow()

    @classmethod
    def from_json(cls, data):
        if 'name' not in data:
            raise ValueError("missing required name field")
        rp = ResearchProtocol.query.filter_by(name=data['name']).first()
        if not rp:
            rp = cls(data['name'])
        return rp

    def as_json(self):
        d = {}
        d['id'] = self.id
        d['resourceType'] = 'ResearchProtocol'
        d['name'] = self.name
        d['created_at'] = FHIR_datetime.as_fhir(self.created_at)
        return d
