"""Research Protocol module"""
from datetime import datetime

from ..database import db
from ..date_tools import FHIR_datetime


class ResearchProtocol(db.Model):
    """ResearchProtocol model for tracking QB versions"""
    __tablename__ = 'research_protocols'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow)

    @classmethod
    def from_json(cls, data):
        if 'name' not in data:
            raise ValueError("missing required name field")
        instance = cls()
        return instance.update_from_json(data)

    def update_from_json(self, data):
        self.name = data['name']
        if 'created_at' in data:
            self.created_at = data['created_at']
        return self

    def as_json(self):
        d = {}
        d['id'] = self.id
        d['resourceType'] = 'ResearchProtocol'
        d['name'] = self.name
        d['created_at'] = FHIR_datetime.as_fhir(self.created_at)
        return d
